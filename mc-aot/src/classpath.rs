//! Índice efímero del classpath de un bundle; no es un cargador Java en ejecución.
use super::{extract, Result};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::{Mutex, OnceLock};
use std::time::{SystemTime, UNIX_EPOCH};

struct TempDir(PathBuf);
impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
fn temp_dir() -> Result<TempDir> {
    let n = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_nanos();
    let path = std::env::temp_dir().join(format!("mc-aot-classpath-{}-{n}", std::process::id()));
    fs::create_dir(&path).map_err(|e| format!("crear directorio temporal: {e}"))?;
    Ok(TempDir(path))
}
struct Entry {
    archive: usize,
    member: String,
}
struct Index {
    archives: Vec<PathBuf>,
    classes: HashMap<String, Entry>,
    services: HashMap<String, Vec<Entry>>,
    _tmp: Option<TempDir>,
}
static CACHE: OnceLock<Mutex<HashMap<PathBuf, Index>>> = OnceLock::new();
fn valid_class(name: &str) -> bool {
    !name.is_empty()
        && name
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || "_$/".contains(c))
        && !name.starts_with('/')
        && !name.split('/').any(|p| p.is_empty())
}
fn manifest_multi_release(path: &Path) -> bool {
    let Ok(bytes) = extract(path, "META-INF/MANIFEST.MF") else {
        return false;
    };
    // JarFile de Java 25 primero busca la secuencia completa en bytes; si está
    // dividida entre líneas, no activa multi-release aunque Attributes la una.
    const MARKER: &[u8] = b"multi-release: true";
    if !bytes
        .windows(MARKER.len())
        .any(|w| w.eq_ignore_ascii_case(MARKER))
    {
        return false;
    }
    // Manifest main section, continuation lines belong to the preceding header.
    let text = String::from_utf8_lossy(&bytes);
    let mut fields: Vec<String> = Vec::new();
    for line in text.lines() {
        let line = line.trim_end_matches('\r');
        if line.is_empty() {
            break;
        }
        if let Some(cont) = line.strip_prefix(' ') {
            if let Some(last) = fields.last_mut() {
                last.push_str(cont)
            } else {
                return false;
            }
        } else {
            fields.push(line.to_owned());
        }
    }
    fields
        .iter()
        .filter_map(|l| l.split_once(": "))
        .any(|(k, v)| k.eq_ignore_ascii_case("Multi-Release") && v.eq_ignore_ascii_case("true"))
}
fn entries(path: &Path) -> Result<(HashMap<String, (u32, String)>, Vec<String>)> {
    let out = Command::new("unzip")
        .arg("-Z")
        .arg("-1")
        .arg(path)
        .output()
        .map_err(|e| format!("no se pudo ejecutar unzip: {e}"))?;
    if !out.status.success() {
        return Err(format!(
            "no se pudo listar JAR {}: {}",
            path.display(),
            String::from_utf8_lossy(&out.stderr).trim()
        ));
    }
    let listing = String::from_utf8_lossy(&out.stdout);
    let has_versions = listing.lines().any(|l| l.starts_with("META-INF/versions/"));
    let mr = has_versions && manifest_multi_release(path);
    let mut result: HashMap<String, (u32, String)> = HashMap::new();
    let mut services = Vec::new();
    for member in listing.lines() {
        if let Some(name) = member.strip_prefix("META-INF/services/") {
            if !name.is_empty()
                && name
                    .bytes()
                    .all(|c| c.is_ascii_alphanumeric() || b"_$.".contains(&c))
            {
                if services.iter().any(|s| s == member) {
                    return Err(format!("recurso de servicio duplicado en un JAR: {member}"));
                }
                services.push(member.to_owned());
            }
        }
        let (version, base) = if let Some(rest) = member.strip_prefix("META-INF/versions/") {
            if !mr {
                continue;
            }
            let Some((version, base)) = rest.split_once('/') else {
                continue;
            };
            let Ok(version) = version.parse::<u32>() else {
                continue;
            };
            if !(9..=25).contains(&version) {
                continue;
            }
            (version, base)
        } else {
            (0, member)
        };
        let Some(name) = base.strip_suffix(".class") else {
            continue;
        };
        if !valid_class(name) {
            continue;
        }
        match result.get(name) {
            Some((old, _)) if *old > version => continue,
            Some((old, _)) if *old == version => {
                return Err(format!("entrada class duplicada: {member}"))
            }
            _ => {}
        }
        result.insert(name.to_owned(), (version, member.to_owned()));
    }
    Ok((result, services))
}
impl Index {
    fn open(jar: &Path) -> Result<Self> {
        let versions = extract(jar, "META-INF/versions.list");
        let (archives, tmp) = if let Ok(versions) = versions {
            let libraries = extract(jar, "META-INF/libraries.list")?;
            let tmp = temp_dir()?;
            let mut paths = Vec::new();
            for (kind, list) in [("versions", versions), ("libraries", libraries)] {
                let list =
                    std::str::from_utf8(&list).map_err(|_| format!("{kind}.list inválido"))?;
                for line in list.lines() {
                    let parts = line.split('\t').collect::<Vec<_>>();
                    if parts.len() != 3 {
                        return Err(format!("entrada inválida en {kind}.list"));
                    }
                    let (expected, nested) = (parts[0], parts[2]);
                    if expected.len() != 64
                        || !expected.bytes().all(|b| b.is_ascii_hexdigit())
                        || nested.is_empty()
                        || nested.starts_with('/')
                        || nested.contains('\\')
                        || nested
                            .split('/')
                            .any(|p| p.is_empty() || p == ".." || p == ".")
                        || nested.chars().any(|c| matches!(c, '*' | '?' | '[' | ']'))
                    {
                        return Err(format!("entrada insegura en {kind}.list"));
                    }
                    let data = extract(jar, &format!("META-INF/{kind}/{nested}"))?;
                    let path = tmp.0.join(format!("{}.jar", paths.len()));
                    fs::write(&path, data).map_err(|e| e.to_string())?;
                    let out = Command::new("sha256sum")
                        .arg(&path)
                        .output()
                        .map_err(|e| e.to_string())?;
                    if !out.status.success() {
                        return Err("sha256sum falló".into());
                    }
                    let text = std::str::from_utf8(&out.stdout)
                        .map_err(|_| "salida sha256sum inválida")?;
                    if !text
                        .split_whitespace()
                        .next()
                        .unwrap_or("")
                        .eq_ignore_ascii_case(expected)
                    {
                        return Err(format!("SHA-256 incorrecto en {kind}/{nested}"));
                    }
                    paths.push(path);
                }
            }
            (paths, Some(tmp))
        } else {
            (vec![jar.to_path_buf()], None)
        };
        let mut classes = HashMap::new();
        let mut services: HashMap<String, Vec<Entry>> = HashMap::new();
        for (archive, path) in archives.iter().enumerate() {
            let (class_entries, service_entries) = entries(path)?;
            for (name, (_, member)) in class_entries {
                classes.entry(name).or_insert(Entry { archive, member });
            }
            for member in service_entries {
                let name = member
                    .strip_prefix("META-INF/services/")
                    .unwrap()
                    .replace('.', "/");
                services
                    .entry(name)
                    .or_default()
                    .push(Entry { archive, member });
            }
        }
        Ok(Index {
            archives,
            classes,
            services,
            _tmp: tmp,
        })
    }
    fn class(&self, name: &str) -> Result<Vec<u8>> {
        let entry = self.classes.get(name).ok_or_else(|| {
            format!("clase no encontrada en versiones ni bibliotecas: {name}.class")
        })?;
        extract(&self.archives[entry.archive], &entry.member)
    }
}
pub(super) fn class_from_jar(jar: &Path, class: &str) -> Result<Vec<u8>> {
    if !valid_class(class) {
        return Err("ruta de clase inválida".into());
    }
    let key =
        fs::canonicalize(jar).map_err(|e| format!("no se pudo abrir {}: {e}", jar.display()))?;
    let cache = CACHE.get_or_init(|| Mutex::new(HashMap::new()));
    let mut indexes = cache.lock().map_err(|_| "índice bloqueado")?;
    if !indexes.contains_key(&key) {
        indexes.insert(key.clone(), Index::open(&key)?);
    }
    indexes[&key].class(class)
}
pub(super) fn has_class(jar: &Path, class: &str) -> Result<bool> {
    if !valid_class(class) {
        return Err("ruta de clase inválida".into());
    }
    let key =
        fs::canonicalize(jar).map_err(|e| format!("no se pudo abrir {}: {e}", jar.display()))?;
    let cache = CACHE.get_or_init(|| Mutex::new(HashMap::new()));
    let mut indexes = cache.lock().map_err(|_| "índice bloqueado")?;
    if !indexes.contains_key(&key) {
        indexes.insert(key.clone(), Index::open(&key)?);
    }
    Ok(indexes[&key].classes.contains_key(class))
}
/// Recursos META-INF/services en orden del classpath; no busca recursos externos.
pub(super) fn services(jar: &Path) -> Result<Vec<(String, Vec<Vec<u8>>)>> {
    let key =
        fs::canonicalize(jar).map_err(|e| format!("no se pudo abrir {}: {e}", jar.display()))?;
    let cache = CACHE.get_or_init(|| Mutex::new(HashMap::new()));
    let mut indexes = cache.lock().map_err(|_| "índice bloqueado")?;
    if !indexes.contains_key(&key) {
        indexes.insert(key.clone(), Index::open(&key)?);
    }
    let index = &indexes[&key];
    let mut result = Vec::new();
    for (name, entries) in &index.services {
        let mut resources = Vec::new();
        for entry in entries {
            resources.push(extract(&index.archives[entry.archive], &entry.member)?);
        }
        result.push((name.clone(), resources));
    }
    result.sort_by(|a, b| a.0.cmp(&b.0));
    Ok(result)
}
pub(super) fn clear() {
    if let Some(cache) = CACHE.get() {
        if let Ok(mut guard) = cache.lock() {
            guard.clear();
        }
    }
}

/// Perfil cerrado: primer version.json plano del classpath, sin variantes multi-release.
pub(super) fn version_resource(jar: &Path) -> Result<Option<Vec<u8>>> {
    let key =
        fs::canonicalize(jar).map_err(|e| format!("no se pudo abrir {}: {e}", jar.display()))?;
    let cache = CACHE.get_or_init(|| Mutex::new(HashMap::new()));
    let mut indexes = cache.lock().map_err(|_| "índice bloqueado")?;
    if !indexes.contains_key(&key) {
        indexes.insert(key.clone(), Index::open(&key)?);
    }
    let index = &indexes[&key];
    for path in &index.archives {
        let out = Command::new("unzip")
            .args(["-Z", "-1"])
            .arg(path)
            .output()
            .map_err(|e| e.to_string())?;
        if !out.status.success() {
            return Err(format!("no se pudo listar {}", path.display()));
        }
        let listing =
            std::str::from_utf8(&out.stdout).map_err(|_| "listado de recursos no UTF-8")?;
        if manifest_multi_release(path)
            && listing
                .lines()
                .any(|l| l.starts_with("META-INF/versions/") && l.ends_with("/version.json"))
        {
            return Err("version.json multi-release no soportado".into());
        }
        let count = listing.lines().filter(|l| *l == "version.json").count();
        if count > 1 {
            return Err("version.json duplicado no soportado".into());
        }
        if count == 1 {
            let bytes = extract(path, "version.json")?;
            if bytes.len() > 1_000_000 {
                return Err("version.json excede límite".into());
            }
            return Ok(Some(bytes));
        }
    }
    Ok(None)
}

/// Solo para una optimización cerrada: no omitir un recurso Log4j existente.
pub(super) fn require_absent_resource(jar: &Path, name: &str) -> Result<()> {
    if name.is_empty() || name.starts_with('/') || name.contains("..") || name.contains('\n') {
        return Err("ruta de recurso inválida".into());
    }
    let key = fs::canonicalize(jar).map_err(|e| e.to_string())?;
    let cache = CACHE.get_or_init(|| Mutex::new(HashMap::new()));
    let mut indexes = cache.lock().map_err(|_| "índice bloqueado")?;
    if !indexes.contains_key(&key) {
        indexes.insert(key.clone(), Index::open(&key)?);
    }
    for path in &indexes[&key].archives {
        let output = Command::new("unzip")
            .args(["-Z", "-1"])
            .arg(path)
            .output()
            .map_err(|e| e.to_string())?;
        if !output.status.success() {
            return Err(format!("no se pudo listar {}", path.display()));
        }
        let listing =
            std::str::from_utf8(&output.stdout).map_err(|_| "listado de recursos no UTF-8")?;
        if listing.lines().any(|s| {
            s == name || (s.starts_with("META-INF/versions/") && s.ends_with(&format!("/{name}")))
        }) {
            return Err(format!(
                "recurso {name} presente o multi-release: ruta Log4j no soportada"
            ));
        }
    }
    Ok(())
}
