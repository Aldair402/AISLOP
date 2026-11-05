#[derive(Clone, Copy)] enum V { I(i32), L(i64), F(f32), D(f64), R(Option<usize>) }
fn pop_i(s:&mut Vec<V>)->i32 {match s.pop().expect("pila vacía") {V::I(x)=>x,_=>panic!("se esperaba int")}}
fn pop_l(s:&mut Vec<V>)->i64 {match s.pop().expect("pila vacía") {V::L(x)=>x,_=>panic!("se esperaba long")}}
fn pop_f(s:&mut Vec<V>)->f32{match s.pop().expect("pila vacía"){V::F(x)=>x,_=>panic!("se esperaba float")}}
fn pop_d(s:&mut Vec<V>)->f64{match s.pop().expect("pila vacía"){V::D(x)=>x,_=>panic!("se esperaba double")}}
fn pop_r(s:&mut Vec<V>)->Option<usize> {match s.pop().expect("pila vacía") {V::R(x)=>x,_=>panic!("se esperaba referencia")}}
fn local_i(v:&[Option<V>],i:usize)->i32 {match v[i] {Some(V::I(x))=>x,_=>panic!("local int sin inicializar")}}
fn local_l(v:&[Option<V>],i:usize)->i64 {match v[i] {Some(V::L(x))=>x,_=>panic!("local long sin inicializar")}}
fn local_f(v:&[Option<V>],i:usize)->f32{match v[i]{Some(V::F(x))=>x,_=>panic!("local float sin inicializar")}}
fn local_d(v:&[Option<V>],i:usize)->f64{match v[i]{Some(V::D(x))=>x,_=>panic!("local double sin inicializar")}}
fn local_r(v:&[Option<V>],i:usize)->Option<usize> {match v[i] {Some(V::R(x))=>x,_=>panic!("local referencia sin inicializar")}}
fn div_i(a:i32,b:i32)->i32 {if b==0 {raise("ArithmeticException","/ by zero");} a.wrapping_div(b)}
fn rem_i(a:i32,b:i32)->i32 {if b==0 {raise("ArithmeticException","/ by zero");} a.wrapping_rem(b)}
fn div_l(a:i64,b:i64)->i64 {if b==0 {raise("ArithmeticException","/ by zero");} a.wrapping_div(b)}
fn rem_l(a:i64,b:i64)->i64 {if b==0 {raise("ArithmeticException","/ by zero");} a.wrapping_rem(b)}
fn int_exact(a:i64)->i32 {i32::try_from(a).unwrap_or_else(|_| {raise("ArithmeticException","integer overflow")})}
fn floor_div_i(a:i32,b:i32)->i32 {let q=div_i(a,b);let r=rem_i(a,b);if r!=0 && (a^b)<0 {q.wrapping_sub(1)} else {q}}
// Valores de Math.asin(i/256) y Math.cos(asin(i/256)) del oráculo Java 25; no es Math general.
static MTH_MATH_JAVA25:[(u64,u64);257]=[
    (0x0000000000000000u64,0x3ff0000000000000u64),
    (0x3f700002aaabdddfu64,0x3fefffeffffbfffeu64),
    (0x3f80000aaabdde0cu64,0x3fefffbfffbfff80u64),
    (0x3f8800240091cfdau64,0x3fefff6ffebbfa4eu64),
    (0x3f90002aabdde94cu64,0x3feffefffbffdfffu64),
    (0x3f94005358ff0bd8u64,0x3feffe6ff63b85e7u64),
    (0x3f980090091d9024u64,0x3feffdbfebbe9360u64),
    (0x3f9c00e4be5f0304u64,0x3feffcefda786870u64),
    (0x3fa000aabde0b9c8u64,0x3feffbffbff7fec0u64),
    (0x3fa200f3229fdf2cu64,0x3feffaef996bc4e8u64),
    (0x3fa4014d8ffaf8afu64,0x3feff9bf63a1740bu64),
    (0x3fa601bc0922e634u64,0x3feff86f1b05dfb0u64),
    (0x3fa8024091fdb0a9u64,0x3feff6febba4bfeau64),
    (0x3faa02dd2f38ebf6u64,0x3feff56e412875abu64),
    (0x3fac0393e65c2c93u64,0x3feff3bda6d9c950u64),
    (0x3fae0466bddb929cu64,0x3feff1ece79fa355u64),
    (0x3fb002abde953619u64,0x3fefeffbfdfebf1fu64),
    (0x3fb103347666f892u64,0x3fefedeae41957e6u64),
    (0x3fb203ce2b380cd3u64,0x3fefebb993aecf99u64),
    (0x3fb3047a02794911u64,0x3fefe968061b4fc8u64),
    (0x3fb405390240e6fdu64,0x3fefe6f634576477u64),
    (0x3fb5060c31541da5u64,0x3fefe46416f790d1u64),
    (0x3fb606f49730ccc5u64,0x3fefe1b1a62bddadu64),
    (0x3fb707f33c173a99u64,0x3fefdeded9bf61d3u64),
    (0x3fb809092913e52eu64,0x3fefdbeba917c3f5u64),
    (0x3fb90a3768096840u64,0x3fefd8d80b34b63eu64),
    (0x3fba0b7f03ba78acu64,0x3fefd5a3f6af6b74u64),
    (0x3fbb0ce107d3f690u64,0x3fefd24f61ba0590u64),
    (0x3fbc0e5e80f7172du64,0x3fefceda421efdb5u64),
    (0x3fbd0ff87cc3a7a5u64,0x3fefcb448d40857cu64),
    (0x3fbe11b009e269b5u64,0x3fefc78e3817e16eu64),
    (0x3fbf1386380f8b9au64,0x3fefc3b73734bca2u64),
    (0x3fc00abe0c129e1eu64,0x3fefbfbf7ebc755fu64),
    (0x3fc08bc95e132e6fu64,0x3fefbba7026962a7u64),
    (0x3fc10ce59ba4a8c4u64,0x3fefb76db58a1299u64),
    (0x3fc18e134f0178afu64,0x3fefb3138b008181u64),
    (0x3fc20f530308cc20u64,0x3fefae987541497fu64),
    (0x3fc290a543442d6au64,0x3fefa9fc6652caa7u64),
    (0x3fc3120a9bed2f46u64,0x3fefa53f4fcc4b79u64),
    (0x3fc3938399f32b5cu64,0x3fefa06122d5118cu64),
    (0x3fc41510cb011423u64,0x3fef9b61d0237250u64),
    (0x3fc496b2bd835ab9u64,0x3fef964147fbdbbfu64),
    (0x3fc5186a00ade974u64,0x3fef90ff7a2fd4d2u64),
    (0x3fc59a37248233eau64,0x3fef8b9c561cf5a1u64),
    (0x3fc61c1ab9d55d30u64,0x3fef8617caabd6f6u64),
    (0x3fc69e1552567517u64,0x3fef8071c64ef938u64),
    (0x3fc720278094cd3cu64,0x3fef7aaa3701a270u64),
    (0x3fc7a251d80666abu64,0x3fef74c10a46b354u64),
    (0x3fc82494ed0e78fcu64,0x3fef6eb62d27730du64),
    (0x3fc8a6f1550413c4u64,0x3fef68898c325199u64),
    (0x3fc92967a638db38u64,0x3fef623b1379a09bu64),
    (0x3fc9abf877ffe0e8u64,0x3fef5bcaae92424eu64),
    (0x3fca2ea462b4998eu64,0x3fef553848924e81u64),
    (0x3fcab16bffc1f0ddu64,0x3fef4e83cc0fad49u64),
    (0x3fcb344fe9a97c4du64,0x3fef47ad231ea746u64),
    (0x3fcbb750bc0acdefu64,0x3fef40b437506b2fu64),
    (0x3fcc3a6f13aae84bu64,0x3fef3998f1b1886cu64),
    (0x3fccbdab8e7bd466u64,0x3fef325b3ac85e81u64),
    (0x3fcd4106cba45b08u64,0x3fef2afafa9380f9u64),
    (0x3fcdc4816b87e25eu64,0x3fef237818880fa4u64),
    (0x3fce481c0fce7134u64,0x3fef1bd27b9002c4u64),
    (0x3fcecbd75b6cd8f0u64,0x3fef140a0a086af1u64),
    (0x3fcf4fb3f2ad079bu64,0x3fef0c1ea9bfa45fu64),
    (0x3fcfd3b27b368330u64,0x3fef04103ff37d41u64),
    (0x3fd02be9ce0b87cdu64,0x3feefbdeb14f4edau64),
    (0x3fd06e0bfee5c057u64,0x3feef389e1ea090du64),
    (0x3fd0b04025245cccu64,0x3feeeb11b5442ff1u64),
    (0x3fd0f28696826d95u64,0x3feee2760e45cb23u64),
    (0x3fd134dfa9805147u64,0x3feed9b6cf3c4663u64),
    (0x3fd1774bb5687cf9u64,0x3feed0d3d9d8432fu64),
    (0x3fd1b9cb12545e62u64,0x3feec7cd0f2b5adfu64),
    (0x3fd1fc5e19315893u64,0x3feebea24fa5d0ecu64),
    (0x3fd23f0523c5dc2bu64,0x3feeb5537b1434dau64),
    (0x3fd281c08cb69be8u64,0x3feeabe0709cf371u64),
    (0x3fd2c490af8bde81u64,0x3feea2490ebdd6b8u64),
    (0x3fd30775e8b6eeb9u64,0x3fee988d33497437u64),
    (0x3fd34a709597aab1u64,0x3fee8eacbb648910u64),
    (0x3fd38d8114823369u64,0x3fee84a78383435du64),
    (0x3fd3d0a7c4c4bd9cu64,0x3fee7a7d6766784bu64),
    (0x3fd413e506ad84eeu64,0x3fee702e4218c668u64),
    (0x3fd457393b90e2aau64,0x3fee65b9edeba38eu64),
    (0x3fd49aa4c5cf8926u64,0x3fee5b20447455cbu64),
    (0x3fd4de2808dce513u64,0x3fee50611e88d6b5u64),
    (0x3fd521c36945a5f2u64,0x3fee457c543ca073u64),
    (0x3fd565774cb66f02u64,0x3fee3a71bcdd63deu64),
    (0x3fd5a9441a02b1fdu64,0x3fee2f412eefa6f9u64),
    (0x3fd5ed2a392bb50fu64,0x3fee23ea802b4b1au64),
    (0x3fd6312a1367c57cu64,0x3fee186d8577f9ecu64),
    (0x3fd675441329986eu64,0x3fee0cca12e97895u64),
    (0x3fd6b978a427db95u64,0x3fee00fffbbbe023u64),
    (0x3fd6fdc83364f719u64,0x3fedf50f124fba75u64),
    (0x3fd742332f3702b4u64,0x3fede8f7282602aeu64),
    (0x3fd786ba074fef93u64,0x3feddcb80ddc085bu64),
    (0x3fd7cb5d2cc5e8edu64,0x3fedd05193273445u64),
    (0x3fd8101d121bed2du64,0x3fedc3c386d0ae09u64),
    (0x3fd854fa2b4aa1a3u64,0x3fedb70db6b0e156u64),
    (0x3fd899f4edc962d3u64,0x3fedaa2fefaae1d8u64),
    (0x3fd8df0dd0979384u64,0x3fed9d29fda7ac9cu64),
    (0x3fd924454c462cc4u64,0x3fed8ffbab9145d5u64),
    (0x3fd9699bdb019139u64,0x3fed82a4c34db1c6u64),
    (0x3fd9af11f89ba61cu64,0x3fed75250db9c792u64),
    (0x3fd9f4a82296347bu64,0x3fed677c52a3dc9bu64),
    (0x3fda3a5ed82d9537u64,0x3fed59aa58c6471cu64),
    (0x3fda80369a63aaa8u64,0x3fed4baee5c1b694u64),
    (0x3fdac62fec0b2a92u64,0x3fed3d89be176072u64),
    (0x3fdb0c4b51d33b86u64,0x3fed2f3aa522ff95u64),
    (0x3fdb5289525368abu64,0x3fed20c15d14a4e5u64),
    (0x3fdb98ea7617ef3au64,0x3fed121da6ea5769u64),
    (0x3fdbdf6f47ae6904u64,0x3fed034f42698214u64),
    (0x3fdc261853b2d785u64,0x3fecf455ee182d6du64),
    (0x3fdc6ce628dd132cu64,0x3fece5316736032eu64),
    (0x3fdcb3d9580ea2b8u64,0x3fecd5e169b519d7u64),
    (0x3fdcfaf27460fe9fu64,0x3fecc665b0328622u64),
    (0x3fdd4232133444adu64,0x3fecb6bdf3eeb01fu64),
    (0x3fdd8998cc3e6049u64,0x3feca6e9ecc569b9u64),
    (0x3fddd127399aabe7u64,0x3fec96e95125c43eu64),
    (0x3fde18ddf7da106bu64,0x3fec86bbd609a260u64),
    (0x3fde60bda613a78fu64,0x3fec76612eed0424u64),
    (0x3fdea8c6e5f5e67fu64,0x3fec65d90dc509f4u64),
    (0x3fdef0fa5bd85625u64,0x3fec552322f6abf5u64),
    (0x3fdf3958aecddef4u64,0x3fec443f1d4d22afu64),
    (0x3fdf81e288b7ae20u64,0x3fec332ca9effdd0u64),
    (0x3fdfca989658baafu64,0x3fec21eb7458e5ccu64),
    (0x3fe009bdc3b4f877u64,0x3fec107b264904d9u64),
    (0x3fe02e46075785a1u64,0x3febfedb67be13b3u64),
    (0x3fe052e571060fd4u64,0x3febed0bdee7064du64),
    (0x3fe0779c5d4df4b8u64,0x3febdb0c30185485u64),
    (0x3fe09c6b2a636bb7u64,0x3febc8dbfdbfda88u64),
    (0x3fe0c152382d7366u64,0x3febb67ae8584caau64),
    (0x3fe0e651e85229ceu64,0x3feba3e88e5c39ecu64),
    (0x3fe10b6a9e43942fu64,0x3feb91248c38986bu64),
    (0x3fe1309cbf4cdb24u64,0x3feb7e2e7c3ed68eu64),
    (0x3fe155e8b2a00052u64,0x3feb6b05f6966b9bu64),
    (0x3fe17b4ee1641318u64,0x3feb57aa912de205u64),
    (0x3fe1a0cfb6c3e9ebu64,0x3feb441bdfab5580u64),
    (0x3fe1c66b9ffd666du64,0x3feb3059735c5e90u64),
    (0x3fe1ec230c714a96u64,0x3feb1c62db2564ffu64),
    (0x3fe211f66db3a5a1u64,0x3feb0837a370523au64),
    (0x3fe237e6379cdfc6u64,0x3feaf3d7561a9c44u64),
    (0x3fe25df2e05b6c41u64,0x3feadf417a62a16du64),
    (0x3fe2841ce0862974u64,0x3feaca7594d44cbdu64),
    (0x3fe2aa64b32f7783u64,0x3feab5732734fa47u64),
    (0x3fe2d0cad5f90e20u64,0x3feaa039b06e926du64),
    (0x3fe2f74fc9289adcu64,0x3fea8ac8ac79d249u64),
    (0x3fe31df40fbd31cdu64,0x3fea751f9447b724u64),
    (0x3fe344b82f859adfu64,0x3fea5f3dddaa0225u64),
    (0x3fe36b9cb13786e1u64,0x3fea4922fb3ac8c2u64),
    (0x3fe392a22087b7e9u64,0x3fea32ce5c4305efu64),
    (0x3fe3b9c90c43296du64,0x3fea1c3f6ca01f29u64),
    (0x3fe3e11206694523u64,0x3fea057594a84fc8u64),
    (0x3fe4087da4473296u64,0x3fe9ee70390dec3cu64),
    (0x3fe4300c7e945024u64,0x3fe9d72ebac16dd6u64),
    (0x3fe457bf318fe517u64,0x3fe9bfb076d236ebu64),
    (0x3fe47f965d201d78u64,0x3fe9a7f4c64dfe15u64),
    (0x3fe4a792a4f26152u64,0x3fe98ffafe1ece30u64),
    (0x3fe4cfb4b09d1a3eu64,0x3fe977c26ee7878au64),
    (0x3fe4f7fd2bc2fb34u64,0x3fe95f4a64decda8u64),
    (0x3fe5206cc637e012u64,0x3fe9469227a84b4cu64),
    (0x3fe5490434275b92u64,0x3fe92d98fa2c355du64),
    (0x3fe571c42e3d0be7u64,0x3fe9145e1a6cf381u64),
    (0x3fe59aad71ced00fu64,0x3fe8fae0c15ad38au64),
    (0x3fe5c3c0c108f95cu64,0x3fe8e12022a5ab3au64),
    (0x3fe5ecfee31c96e7u64,0x3fe8c71b6c8c49b4u64),
    (0x3fe61668a46ffa82u64,0x3fe8acd1c7a997f1u64),
    (0x3fe63ffed6d198f6u64,0x3fe8924256bf4545u64),
    (0x3fe669c251ad69e7u64,0x3fe8776c367dda86u64),
    (0x3fe693b3f244ee17u64,0x3fe85c4e7d4a0bb1u64),
    (0x3fe6bdd49bea05ceu64,0x3fe840e83aff1d1du64),
    (0x3fe6e825383cc40bu64,0x3fe8253878ae2e09u64),
    (0x3fe712a6b76c6e92u64,0x3fe8093e385a3700u64),
    (0x3fe73d5a107bde74u64,0x3fe7ecf874b086dfu64),
    (0x3fe76840418978a7u64,0x3fe7d06620bd8524u64),
    (0x3fe7935a501afa78u64,0x3fe7b386279d7bf3u64),
    (0x3fe7bea9496d5a54u64,0x3fe796576c292765u64),
    (0x3fe7ea2e42c9027au64,0x3fe778d8c89dc27cu64),
    (0x3fe815ea59dab0a2u64,0x3fe75b090e40447au64),
    (0x3fe841deb5114bb4u64,0x3fe73ce704fb7b23u64),
    (0x3fe86e0c84010764u64,0x3fe71e716af8a794u64),
    (0x3fe89a74ffcc34a4u64,0x3fe6ffa6f4323c0du64),
    (0x3fe8c7196b9225deu64,0x3fe6e0864a0050d6u64),
    (0x3fe8f3fb14e496b4u64,0x3fe6c10e0a9e5d66u64),
    (0x3fe9211b54441083u64,0x3fe6a13cc8a9b946u64),
    (0x3fe94e7b8da3cf7au64,0x3fe681110a985d4du64),
    (0x3fe97c1d30f5b7d2u64,0x3fe660894a2751ccu64),
    (0x3fe9aa01babef75eu64,0x3fe63fa3f3c02962u64),
    (0x3fe9d82ab4b5fdfdu64,0x3fe61e5f65d4d978u64),
    (0x3fea0699b66a8718u64,0x3fe5fcb9f031317bu64),
    (0x3fea355065f87fa4u64,0x3fe5dab1d341202au64),
    (0x3fea645078c6a78cu64,0x3fe5b8453f4ae294u64),
    (0x3fea939bb451e2a0u64,0x3fe59572539c229bu64),
    (0x3feac333ef06451au64,0x3fe572371da8f26eu64),
    (0x3feaf31b1127022eu64,0x3fe54e91981b7778u64),
    (0x3feb235315c680dcu64,0x3fe52a7fa9d2f8eau64),
    (0x3feb53de0bcffc24u64,0x3fe505ff24d0e46bu64),
    (0x3feb84be172438efu64,0x3fe4e10dc51235a7u64),
    (0x3febb5f571cb0571u64,0x3fe4bba92f53830au64),
    (0x3febe7866d3b6480u64,0x3fe495ceefbdc28bu64),
    (0x3fec197373bc7bf1u64,0x3fe46f7c7879a3bcu64),
    (0x3fec4bbf09e19830u64,0x3fe448af2027201cu64),
    (0x3fec7e6bd023da76u64,0x3fe4216420369e50u64),
    (0x3fecb17c849c7288u64,0x3fe3f9989320b7f7u64),
    (0x3fece4f404e29b3au64,0x3fe3d14972795a11u64),
    (0x3fed18d55010f295u64,0x3fe3a87394da947au64),
    (0x3fed4d2388f6360bu64,0x3fe37f13aba2fbb6u64),
    (0x3fed81e1f875ea8du64,0x3fe355264082fea0u64),
    (0x3fedb714101e0a0eu64,0x3fe32aa7b2d3fd8fu64),
    (0x3fedecbd6cf77786u64,0x3fe2ff9434b34639u64),
    (0x3fee22e1da97bb17u64,0x3fe2d3e7c7da540au64),
    (0x3fee5985567b665du64,0x3fe2a79e3a2cd2e6u64),
    (0x3fee90ac13b18234u64,0x3fe27ab321f3dcf1u64),
    (0x3feec85a7ee191dau64,0x3fe24d21d9bcbd2du64),
    (0x3fef009542b712f2u64,0x3fe21ee57bd01fd8u64),
    (0x3fef39614cbef7d4u64,0x3fe1eff8dd34fde3u64),
    (0x3fef72c3d2c5752au64,0x3fe1c0568830ae9du64),
    (0x3fefacc258c4aaf9u64,0x3fe18ff8b63353dcu64),
    (0x3fefe762b77744d5u64,0x3fe15ed9491d3888u64),
    (0x3ff0115591d29d12u64,0x3fe12cf1c3c6a214u64),
    (0x3ff02f511b223c0fu64,0x3fe0fa3b41afe8acu64),
    (0x3ff04da77ac5c9e5u64,0x3fe0c6ae6dbb479du64),
    (0x3ff06c5c6f8ce9ccu64,0x3fe0924377cc95c0u64),
    (0x3ff08b73f9af1058u64,0x3fe05cf20924c255u64),
    (0x3ff0aaf2613700b3u64,0x3fe026b137474acau64),
    (0x3ff0cadc3d4378b1u64,0x3fdfdeeeea5d2083u64),
    (0x3ff0eb367c3fd618u64,0x3fdf6e75051127beu64),
    (0x3ff10c066d3e6932u64,0x3fdefbdeb14f4ed9u64),
    (0x3ff12d51caa6b58bu64,0x3fde87142982b1b2u64),
    (0x3ff14f1ec67484edu64,0x3fde0ffbbe00c34fu64),
    (0x3ff1717418520341u64,0x3fdd96799ba6f66cu64),
    (0x3ff194590de7e7f6u64,0x3fdd1a6f89821640u64),
    (0x3ff1b7d59dd40ba2u64,0x3fdc9bbc9bb903fcu64),
    (0x3ff1dbf27dd2221au64,0x3fdc1a3cd9862dfcu64),
    (0x3ff200b93cc5a540u64,0x3fdb95c8d37c8daau64),
    (0x3ff2263461820ad8u64,0x3fdb0e35269b38f4u64),
    (0x3ff24c6f8f6affb2u64,0x3fda8351e7be222bu64),
    (0x3ff27377b2570a1eu64,0x3fd9f4e9f1b5859eu64),
    (0x3ff29b5b338b7c8du64,0x3fd962c20e982feau64),
    (0x3ff2c42a3a3c7a87u64,0x3fd8cc97f2912db7u64),
    (0x3ff2edf6fac7f5b8u64,0x3fd83220fb33564eu64),
    (0x3ff318d619008ed9u64,0x3fd79308a1dd964bu64),
    (0x3ff344df237486d7u64,0x3fd6eeee8953be07u64),
    (0x3ff3722d2feb24c8u64,0x3fd645640568c1c3u64),
    (0x3ff3a0dfa4bb4affu64,0x3fd595e8ede2700cu64),
    (0x3ff3d11b3fc3b697u64,0x3fd4dfe7790ba697u64),
    (0x3ff4030b73c55372u64,0x3fd422aeba618155u64),
    (0x3ff436e4418e69c0u64,0x3fd35d6b2ed1914au64),
    (0x3ff46ce4c738c4eau64,0x3fd28f1c6c540fb9u64),
    (0x3ff4a55ae332c7a5u64,0x3fd1b6867c415165u64),
    (0x3ff4e0a887c40a9cu64,0x3fd0d21c6aeb714fu64),
    (0x3ff51f4bd13f8591u64,0x3fcfbfbf7ebc755du64),
    (0x3ff561ebd9c18cd3u64,0x3fcdba59d10bfe0au64),
    (0x3ff5a96e34bc532bu64,0x3fcb8cc9d3952a43u64),
    (0x3ff5f71d7ff42c8au64,0x3fc92ca4f010700eu64),
    (0x3ff64cf55148366eu64,0x3fc689f26c6b01d5u64),
    (0x3ff6ae4c63222736u64,0x3fc389d6226c1299u64),
    (0x3ff721a5d8718655u64,0x3fbfeffbfdfebf21u64),
    (0x3ff7b7d33b928c5bu64,0x3fb69af589b35960u64),
    (0x3ff921fb54442d18u64,0x3c91a62633145c07u64)
];
fn mth_asin(v:f64)->f64{let scaled=v*256.0;if !scaled.is_finite()||scaled<0.0||scaled>256.0||scaled.fract()!=0.0||v.to_bits()!=((scaled as usize) as f64/256.0).to_bits(){error("Math.asin: argumento fuera del perfil Mth Java 25");}f64::from_bits(MTH_MATH_JAVA25[scaled as usize].0)}
fn mth_cos(v:f64)->f64{for (asin,cos) in MTH_MATH_JAVA25{if asin==v.to_bits(){return f64::from_bits(cos);}}error("Math.cos: argumento fuera del perfil Mth Java 25")}
fn floor_mod_i(a:i32,b:i32)->i32 {let r=rem_i(a,b);if r!=0 && (a^b)<0 {r.wrapping_add(b)} else {r}}
fn floor_div_l(a:i64,b:i64)->i64 {let q=div_l(a,b);let r=rem_l(a,b);if r!=0 && (a^b)<0 {q.wrapping_sub(1)} else {q}}
fn floor_mod_l(a:i64,b:i64)->i64 {let r=rem_l(a,b);if r!=0 && (a^b)<0 {r.wrapping_add(b)} else {r}}

enum Array { Z(Vec<bool>), B(Vec<i8>), C(Vec<u16>), S(Vec<i16>), I(Vec<i32>), J(Vec<i64>), F(Vec<f32>), D(Vec<f64>), Strings(Vec<Option<usize>>), Str(Vec<u16>), Boolean(bool), Integer(i32), Long(i64), Byte(i8), Short(i16), Character(u16), Float(f32), Double(f64), StackOption, TimeUnit(u8), StackWalker(bool), StackWalkStream(Vec<&'static str>,usize,bool,usize,bool), StackStage(usize,bool,u8,usize), StackFrame(&'static str,bool), Duration(i64,i32), CompletedFuture(Option<usize>), AtomicRef(Option<usize>), AtomicLong(i64), AtomicInteger(i32), ReentrantLock(i32), ReadWriteLock(i32,i32,Option<usize>,Option<usize>), ReadLock(usize), WriteLock(usize), CurrentProcess, CurrentThread(bool,usize), RuntimeSingleton, RuntimePermission(Option<usize>), WeakLoader(Option<usize>), Collector(usize,usize,usize), JoinCollector(Option<usize>,Option<usize>,Option<usize>), Comparing(usize), BaseModule, BootLayer, JfrModule, Lambda(usize,&'static str,Vec<V>), IdentityFunction, IsoInstantFormatter, RootLocale, Path(String,Option<usize>), File(Option<String>,Option<usize>), CrashDateFormatter, Optional(Option<usize>), Pattern(usize,i32), Matcher(usize,usize,Option<(usize,usize,Option<(usize,usize)>)>), Uuid([u8;16]), Date(i64), Zoned(i64,i32), Instant(i64,i32), ResourceStream(&'static [u8],usize,bool), ByteInput(Option<usize>,usize,usize,usize), FileInput(Option<std::fs::File>), FileOutput(Option<std::fs::File>), Uri(usize), Properties(std::collections::HashMap<Vec<u16>,usize>), PropertiesEntries(usize), PropertiesEmptyIter(usize), Utf8Charset, Reader(Option<usize>,Option<Vec<u16>>,usize,bool), Builder(Vec<u16>), Stdout, Stderr, Exception(&'static str,&'static str,Option<usize>), Obj(&'static str,Vec<V>), SharedObj(&'static str,NumericObjectHandle), LocalObj(&'static str,Vec<V>,Option<usize>), Map(Vec<(usize,usize)>,usize,bool), HashMap(Vec<(Option<usize>,Option<usize>)>), IdentityMap(Vec<(Option<usize>,Option<usize>)>), IdentitySet(usize), LinkedMap(Vec<(Option<usize>,Option<usize>)>,i32), LinkedIter(usize,Vec<Option<usize>>,usize,i32), TreeMap(Vec<(usize,Option<usize>)>,i32), TreeEntries(usize), TreeEntry(usize,usize,i32), TreeIter(usize,Vec<usize>,usize,i32,bool), EmptyMap, EnumSet(Vec<usize>), EnumSetIter(Vec<usize>,usize), EmptyList, EmptySet, ImmutableList(Vec<Option<usize>>), EmptyIterator, MapValues(usize), Queue(std::collections::VecDeque<usize>), ConcurrentQueue(std::collections::VecDeque<usize>), Deque(std::collections::VecDeque<usize>), Local(Option<usize>), SuppliedLocal(usize,Option<Option<usize>>), Class(&'static str), List(Vec<Option<usize>>,i32), ArraysList(usize), ArraysListIter(usize,usize), Set(Vec<Option<usize>>,i32), HashSet(Vec<Option<usize>>,i32), KeySet(Vec<Option<usize>>,i32), AppLoader, PlatformLoader, Refs(u8,Vec<Option<usize>>), ProjectRefs(&'static str,Vec<Option<usize>>), Constructor(&'static str), ReflectMethod(usize), Service(&'static str,&'static [&'static str],usize,Vec<usize>), ServiceIter(usize,usize), LazyStream(usize,bool,Option<usize>,bool), SortedStream(usize,bool,usize), MappedStream(usize,bool,usize), StreamSink(Vec<usize>,usize), ListIter(usize,usize,i32), SetIter(usize,Vec<Option<usize>>,usize,i32), EmptyEnumeration }
impl Array {
    fn len(&self)->usize {match self {Self::Z(v)=>v.len(),Self::B(v)=>v.len(),Self::C(v)=>v.len(),Self::S(v)=>v.len(),Self::I(v)=>v.len(),Self::J(v)=>v.len(),Self::F(v)=>v.len(),Self::D(v)=>v.len(),Self::Strings(v)=>v.len(),Self::Refs(_,v)=>v.len(),Self::ProjectRefs(_,v)=>v.len(),_=>panic!("se esperaba array")}}
}
#[derive(Default)] struct Heap { bridge_owner:std::sync::Arc<()>, arrays:Vec<Array>, elements:usize, fields:Vec<V>, interfaces:&'static [(&'static str,&'static str)], init_states:Vec<u8>, intern:std::collections::HashMap<Vec<u16>,usize>, stdout:Option<usize>, stderr:Option<usize>, properties:Option<std::collections::HashMap<Vec<u16>,usize>>, classes:std::collections::HashMap<&'static str,usize>, simple_names:std::collections::HashMap<&'static str,usize>, monitors:std::collections::HashMap<usize,usize>, app_loader:Option<usize>, platform_loader:Option<usize>, context_loader:Option<Option<usize>>, time_units:[Option<usize>;7], enum_values:std::collections::HashMap<usize,(Option<usize>,i32)>, enum_directories:std::collections::HashMap<&'static str,Vec<(usize,usize)>>, causes:std::collections::HashMap<usize,usize>, suppressed:std::collections::HashMap<usize,Vec<usize>>, map_views:std::collections::HashMap<usize,usize>, booleans:[Option<usize>;2], parents:std::collections::HashMap<&'static str,&'static str>, exception_messages:std::collections::HashMap<usize,Option<usize>>, uri_syntax:std::collections::HashMap<usize,(usize,usize,i32)>, uri_schemes:std::collections::HashMap<usize,usize>, uri_paths:std::collections::HashMap<usize,usize>, stack_option:Option<usize>, default_stack_walker:Option<usize>, duration_zero:Option<usize>, integers:std::collections::HashMap<i32,usize>, longs:std::collections::HashMap<i64,usize>, bytes:std::collections::HashMap<i8,usize>, shorts:std::collections::HashMap<i16,usize>, characters:std::collections::HashMap<u16,usize>, tree_entry_views:std::collections::HashMap<usize,usize>, active_maps:Vec<usize>, identity_function:Option<usize>, iso_instant:Option<usize>, root_locale:Option<usize>, builder_caps:std::collections::HashMap<usize,(i32,bool)>, optional_empty:Option<usize>, utf8_charset:Option<usize>, empty_map:Option<usize>, empty_list:Option<usize>, empty_set:Option<usize>, immutable_empty:Option<usize>, empty_iterator:Option<usize>, current_process:Option<usize>, runtime_singleton:Option<usize>, line_separator:Option<usize>, base_module:Option<usize>, boot_layer:Option<usize>, jfr_module:Option<usize>, lambdas:std::collections::HashMap<usize,usize>, spliterators:std::collections::HashMap<usize,(i64,i32)>, walk_scopes:Vec<bool> }
fn error(label:&str)->! { eprintln!("{label}");std::process::exit(2) }
// Guarda explícita del runtime experimental; no simula StackOverflowError.
thread_local! {static JAVA_STACK:std::cell::RefCell<Vec<&'static str>>=const{std::cell::RefCell::new(Vec::new())};}
struct CallGuard;
impl Drop for CallGuard{fn drop(&mut self){JAVA_STACK.with(|s|{s.borrow_mut().pop().expect("pila Java vacía");});}}
fn call_guard(class:&'static str)->CallGuard{JAVA_STACK.with(|s|{let mut frames=s.borrow_mut();if frames.len()>=256{error("límite experimental de recursión excedido");}frames.push(class);});CallGuard}
fn stack_option(h:&mut Heap)->usize{if let Some(id)=h.stack_option{return id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::StackOption);h.stack_option=Some(id);id}
fn stack_walker_new(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);if !matches!(h.arrays[id],Array::StackOption){error("StackWalker: opción no soportada");}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let walker=h.arrays.len();h.arrays.push(Array::StackWalker(true));walker}
fn default_stack_walker(h:&mut Heap)->usize{if let Some(id)=h.default_stack_walker{return id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::StackWalker(false));h.default_stack_walker=Some(id);id}
// Stack frames beyond translated calls or crossing unknown JDK callbacks are rejected.
fn stack_walk(h:&mut Heap,r:Option<usize>,fun:Option<usize>,apply:fn(&mut Heap,Option<usize>,Option<usize>)->Option<usize>)->Option<usize>{
    let id=array_id(h,r);let retain=match h.arrays[id]{Array::StackWalker(v)=>v,_=>error("StackWalker.walk: receptor fuera del perfil")};array_id(h,fun);
    let frames=JAVA_STACK.with(|s|s.borrow().iter().rev().copied().collect::<Vec<_>>());if h.arrays.len()>=10000||h.walk_scopes.len()>=10000||h.elements.saturating_add(frames.len())>1_000_000{error("Límite experimental de heap excedido");}h.elements+=frames.len();let scope=h.walk_scopes.len();h.walk_scopes.push(true);let stream=h.arrays.len();h.arrays.push(Array::StackWalkStream(frames,0,false,scope,retain));
    let result=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||{let _opaque=call_guard("<jdk-callback>");apply(h,fun,Some(stream))}));h.walk_scopes[scope]=false;match result{Ok(v)=>v,Err(p)=>std::panic::resume_unwind(p)}
}
fn stack_stream_skip(h:&mut Heap,r:Option<usize>,count:i64)->usize{let id=array_id(h,r);if count<0{let text=new_string(h,count.to_string().encode_utf16().collect());let ex=new_exception(h,"IllegalArgumentException");init_exception(h,Some(ex),"IllegalArgumentException",Some(text));throw_ref(h,Some(ex));}if count==0{return id;}let (frames,start,scope,retain)=match &h.arrays[id]{Array::StackWalkStream(frames,start,false,scope,retain)=>(frames.clone(),*start,*scope,*retain),Array::StackWalkStream(_,_,true,_,_)=>raise("IllegalStateException","stream has already been operated upon or closed"),_=>error("Stream.skip: solo StackWalker soportado")};if !h.walk_scopes[scope]{error("StackWalker: consumo fuera de walk no modelado");}let start=start.saturating_add(usize::try_from(count).unwrap_or(usize::MAX));if h.arrays.len()>=10000||h.elements.saturating_add(frames.len())>1_000_000{error("Límite experimental de heap excedido");}h.elements+=frames.len();if let Array::StackWalkStream(_,_,linked,_,_)=&mut h.arrays[id]{*linked=true;}let out=h.arrays.len();h.arrays.push(Array::StackWalkStream(frames,start,false,scope,retain));out}
// StackWalker stages are lazy; the true end of the external stack is unknown.
fn stack_stage_new(h:&mut Heap,r:Option<usize>,function:Option<usize>,kind:u8)->usize{let id=array_id(h,r);let f=array_id(h,function);match (kind,&h.arrays[f]){(0,Array::Lambda(_,"java/util/function/Function",_))|(0,Array::IdentityFunction)|(1,Array::Lambda(_,"java/util/function/Predicate",_))=>{},_=>error("StackWalker stream: callback fuera del perfil")};let mut cur=id;let scope=loop{match h.arrays[cur]{Array::StackWalkStream(_,_,_,scope,_)=>break scope,Array::StackStage(parent,_,_,_)=>cur=parent,_=>error("StackWalker stream: fuente fuera del perfil")}};if !h.walk_scopes[scope]{error("StackWalker: consumo fuera de walk no modelado");}match &mut h.arrays[id]{Array::StackWalkStream(_,_,linked,_,_)|Array::StackStage(_,linked,_,_)=>{if *linked{raise("IllegalStateException","stream has already been operated upon or closed");}*linked=true;},_=>unreachable!()};if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let out=h.arrays.len();h.arrays.push(Array::StackStage(id,false,kind,f));out}
fn stack_stream_find_first(h:&mut Heap,r:Option<usize>,apply:fn(&mut Heap,Option<usize>,Option<usize>)->Option<usize>,test:fn(&mut Heap,Option<usize>,Option<usize>)->i32)->usize{let id=array_id(h,r);match h.arrays[id]{Array::StackWalkStream(_,_,false,_,_)|Array::StackStage(_,false,_,_)=>{},Array::StackWalkStream(_,_,true,_,_)|Array::StackStage(_,true,_,_)=>raise("IllegalStateException","stream has already been operated upon or closed"),_=>error("Stream.findFirst: solo StackWalker soportado")};let mut stages=Vec::new();let mut cur=id;let (frames,start,scope,retain)=loop{match &h.arrays[cur]{Array::StackWalkStream(frames,start,_,scope,retain)=>break(frames.clone(),*start,*scope,*retain),Array::StackStage(parent,_,kind,f)=>{stages.push((*kind,*f,true));cur=*parent;},_=>error("StackWalker: pipeline inválido")}};if !h.walk_scopes[scope]{error("StackWalker: consumo fuera de walk no modelado");}stages.reverse();match &mut h.arrays[id]{Array::StackWalkStream(_,_,linked,_,_)|Array::StackStage(_,linked,_,_)=>*linked=true,_=>unreachable!()};for name in frames.iter().skip(start).copied(){if name=="<jdk-callback>"{error("StackWalker: frame JDK no modelado");}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let frame=h.arrays.len();h.arrays.push(Array::StackFrame(name,retain));let mut value=Some(frame);let mut dropped=false;for (kind,f,dropping) in &mut stages{match *kind{0=>{let _opaque=call_guard("<jdk-callback>");value=apply(h,Some(*f),value);},1=>{if *dropping{let result={let _opaque=call_guard("<jdk-callback>");test(h,Some(*f),value)};if result!=0{dropped=true;break;}*dropping=false;}},_=>unreachable!()}}if !dropped{if value.is_none(){raise("NullPointerException","");}return optional_new(h,value);}}error("StackWalker: frames externos no modelados")}

fn stack_frame_class_name(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);let name=match h.arrays[id]{Array::StackFrame(name,_)=>name,_=>error("StackFrame: receptor fuera del perfil")};let cls=class_literal(h,name);class_get_name(h,Some(cls))}
fn stack_frame_class(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);let name=match h.arrays[id]{Array::StackFrame(name,true)=>name,Array::StackFrame(_,false)=>raise("UnsupportedOperationException","No access to RETAIN_CLASS_REFERENCE"),_=>error("StackFrame: receptor fuera del perfil")};class_literal(h,name)}
fn stack_caller_class(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);match h.arrays[id]{Array::StackWalker(true)=>{},Array::StackWalker(false)=>raise("UnsupportedOperationException","No access to RETAIN_CLASS_REFERENCE"),_=>error("StackWalker concreto no soportado")};
    let caller=JAVA_STACK.with(|s|{let frames=s.borrow();if frames.len()<2{error("StackWalker: llamante externo no modelado");}frames[frames.len()-2]});
    if caller=="<jdk-callback>"{error("StackWalker: frame JDK no modelado");}class_literal(h,caller)
}
fn array_new(h:&mut Heap, kind:u8, n:i32)->usize {
    if n<0 {raise("NegativeArraySizeException","");}
    let n=n as usize;
    if h.arrays.len()>=10000 || h.elements.checked_add(n).map_or(true,|v|v>1_000_000) {error("Límite experimental de arrays excedido");}
    let a=match kind {4=>Array::Z(vec![false;n]),5=>Array::C(vec![0;n]),6=>Array::F(vec![0.0;n]),7=>Array::D(vec![0.0;n]),8=>Array::B(vec![0;n]),9=>Array::S(vec![0;n]),10=>Array::I(vec![0;n]),11=>Array::J(vec![0;n]),12=>Array::Strings(vec![None;n]),13|14=>Array::Refs(kind,vec![None;n]),_=>panic!("tipo array inválido")};
    let id=h.arrays.len();h.arrays.push(a);h.elements+=n;id
}
fn project_array_new(h:&mut Heap,class:&'static str,n:i32)->usize {
    if n<0 {raise("NegativeArraySizeException","");}let n=n as usize;
    if h.arrays.len()>=10000||h.elements.checked_add(n).map_or(true,|v|v>1_000_000){error("Límite experimental de arrays excedido");}
    let id=h.arrays.len();h.elements+=n;h.arrays.push(Array::ProjectRefs(class,vec![None;n]));id
}
fn ref_array_copy_of(h:&mut Heap,r:Option<usize>,n:i32)->usize{let id=array_id(h,r);if !matches!(h.arrays[id],Array::Strings(_)|Array::Refs(_,_)|Array::ProjectRefs(_,_)){error("Arrays.copyOf: fuente no es array de referencias");}if n<0{let msg=new_string(h,n.to_string().encode_utf16().collect());let ex=new_exception(h,"NegativeArraySizeException");init_exception(h,Some(ex),"NegativeArraySizeException",Some(msg));throw_ref(h,Some(ex));}let n=n as usize;if h.arrays.len()>=10000||h.elements.checked_add(n).map_or(true,|v|v>1_000_000){error("Arrays.copyOf: límite experimental de arrays excedido");}let a=match &h.arrays[id]{Array::Strings(v)=>{let mut out=v[..v.len().min(n)].to_vec();out.resize(n,None);Array::Strings(out)},Array::Refs(k,v)=>{let mut out=v[..v.len().min(n)].to_vec();out.resize(n,None);Array::Refs(*k,out)},Array::ProjectRefs(c,v)=>{let mut out=v[..v.len().min(n)].to_vec();out.resize(n,None);Array::ProjectRefs(c,out)},_=>unreachable!()};let out=h.arrays.len();h.arrays.push(a);h.elements+=n;out}
fn ref_array_clone(h:&mut Heap,r:Option<usize>)->usize {
    let id=array_id(h,r);let a=match &h.arrays[id] {Array::Strings(v)=>Array::Strings(v.clone()),Array::Refs(k,v)=>Array::Refs(*k,v.clone()),Array::ProjectRefs(c,v)=>Array::ProjectRefs(c,v.clone()),_=>panic!("clone requiere array de referencia")};
    let n=a.len();if h.arrays.len()>=10000||h.elements.checked_add(n).map_or(true,|v|v>1_000_000){error("Límite experimental de arrays excedido");}
    let id=h.arrays.len();h.elements+=n;h.arrays.push(a);id
}
fn jdk_empty_array_new(h:&mut Heap,class:&'static str,n:i32)->usize{if n<0{raise("NegativeArraySizeException","");}if n!=0{error("array JDK tipado: solo longitud cero soportada");}project_array_new(h,class,n)}
fn project_empty_array_new(h:&mut Heap,class:&'static str,n:i32)->usize{if n<0{raise("NegativeArraySizeException","");}if n!=0{error(&format!("array de clase no final: solo longitud cero soportada: {class}"));}project_array_new(h,class,n)}
fn project_nonfinal_array_instance(h:&Heap,r:Option<usize>,class:&str)->bool{match r.and_then(|id|h.arrays.get(id)){Some(Array::ProjectRefs(actual,_)) if *actual==class=>true,Some(Array::ProjectRefs(actual,_)) if !actual.starts_with("java/")&&!actual.starts_with("javax/")=>error("cast covariante de array no soportado"),_=>false}}
fn char_sequence_to_string(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);match &h.arrays[id]{Array::Str(_)=>id,Array::Builder(_)=>builder_to_string(h,r),_=>error("CharSequence.toString: receptor fuera del perfil")}}
fn char_sequence_subsequence(h:&mut Heap,r:Option<usize>,begin:i32,end:i32)->usize{let id=array_id(h,r);match &h.arrays[id]{Array::Str(_)=>string_substring(h,r,begin,Some(end)),Array::Builder(v)=>{if begin<0||end<begin||end as usize>v.len(){raise("StringIndexOutOfBoundsException","");}if begin==end{return string_literal(h,&[]);}let units=v[begin as usize..end as usize].to_vec();new_string(h,units)},_=>error("CharSequence.subSequence: receptor fuera del perfil")}}
fn char_sequence_length(h:&Heap,r:Option<usize>)->i32{let id=array_id(h,r);match &h.arrays[id]{Array::Str(v)|Array::Builder(v)=>v.len() as i32,_=>error("CharSequence concreto no soportado")}}
fn char_sequence_at(h:&Heap,r:Option<usize>,i:i32)->i32{let id=array_id(h,r);let v=match &h.arrays[id]{Array::Str(v)|Array::Builder(v)=>v,_=>error("CharSequence concreto no soportado")};if i<0||i as usize>=v.len(){raise("StringIndexOutOfBoundsException","");}v[i as usize] as i32}
fn collection_instance(h:&Heap,r:Option<usize>,interfaces:&[(&str,&str)])->bool{match r.and_then(|id|h.arrays.get(id)){Some(Array::List(_,_)|Array::Set(_,_)|Array::HashSet(_,_)|Array::KeySet(_,_)|Array::IdentitySet(_)|Array::ImmutableList(_)|Array::EmptyList|Array::EmptySet|Array::EnumSet(_)|Array::TreeEntries(_)|Array::PropertiesEntries(_)|Array::MapValues(_)|Array::ArraysList(_)|Array::Queue(_)|Array::ConcurrentQueue(_)|Array::Deque(_))=>true,Some(Array::Obj(_,_)|Array::SharedObj(_,_)|Array::LocalObj(_,_,_)|Array::Exception(_,_,_))=>project_instance(h,r,"java/util/Collection",interfaces),_=>false}}
fn accessible_check(h:&Heap,r:Option<usize>)->usize{let id=array_id(h,r);if !matches!(h.arrays[id],Array::Constructor(_)|Array::ReflectMethod(_)){error("AccessibleObject: receptor fuera del perfil");}id}
fn accessible_is_accessible(h:&Heap,r:Option<usize>)->bool{accessible_check(h,r);false}
fn accessible_set(h:&Heap,r:Option<usize>,flag:i32){accessible_check(h,r);if flag&1!=0{error("AccessibleObject.setAccessible(true): acceso no verificado");}}
fn member_modifiers(h:&Heap,r:Option<usize>,ctors:&[(&str,i32)],methods:&[i32])->i32{let id=array_id(h,r);match h.arrays[id]{Array::Constructor(c)=>ctors.iter().find(|(n,_)|*n==c).map(|(_,f)|*f).unwrap_or_else(||error("Member.getModifiers: constructor no registrado")),Array::ReflectMethod(i)=>*methods.get(i).unwrap_or_else(||error("Member.getModifiers: método no registrado")),_=>error("Member.getModifiers: receptor fuera del perfil")}}
fn member_declaring_class(h:&mut Heap,r:Option<usize>,methods:&[(&'static str,&'static str,&'static str)])->usize{let id=array_id(h,r);let name=match h.arrays[id]{Array::Constructor(c)=>c,Array::ReflectMethod(i)=>methods.get(i).map(|m|m.0).unwrap_or_else(||error("Member.getDeclaringClass: método no registrado")),_=>error("Member.getDeclaringClass: receptor fuera del perfil")};class_literal(h,name)}
fn member_instance(h:&Heap,r:Option<usize>)->bool{match r.and_then(|id|h.arrays.get(id)){Some(Array::Constructor(_)|Array::ReflectMethod(_))=>true,Some(Array::Obj(_,_)|Array::SharedObj(_,_)|Array::LocalObj(_,_,_))=>error("Member: objeto proyecto no verificado"),Some(Array::Exception(kind,_,_)) if kind.contains('/')=>error("Member: excepción proyecto no verificada"),_=>false}}
fn date_instance(h:&Heap,r:Option<usize>)->bool{match r.and_then(|id|h.arrays.get(id)){Some(Array::Date(_))=>true,Some(Array::Obj(_,_)|Array::SharedObj(_,_)|Array::LocalObj(_,_,_))=>error("Date: objeto proyecto no verificado"),Some(Array::Exception(kind,_,_)) if kind.contains('/')=>error("Date: excepción proyecto no verificada"),_=>false}}
fn temporal_instance(h:&Heap,r:Option<usize>)->bool{match r.and_then(|id|h.arrays.get(id)){Some(Array::Instant(_,_)|Array::Zoned(_,_))=>true,Some(Array::Obj(_,_)|Array::SharedObj(_,_)|Array::LocalObj(_,_,_))=>error("Temporal: objeto proyecto no verificado"),Some(Array::Exception(kind,_,_)) if kind.contains('/')=>error("Temporal: excepción proyecto no verificada"),_=>false}}
fn path_instance(h:&Heap,r:Option<usize>)->bool{match r.and_then(|id|h.arrays.get(id)){Some(Array::Path(_,_))=>true,Some(Array::Obj(_,_)|Array::SharedObj(_,_)|Array::LocalObj(_,_,_))=>error("Path: objeto de proyecto no verificado"),_=>false}}
// Perfil Linux y UTF-8 válido; errores de E/S aún se rechazan, sin fingir IOException.
fn path_of(h:&mut Heap,first:Option<usize>,more:Option<usize>)->usize{
    if !cfg!(target_os="linux"){error("Path.of: solo Linux");}
    let initial=String::from_utf16(string_units(h,first)).unwrap_or_else(|_|error("Path.of: UTF-16 no representable"));
    let id=array_id(h,more);let rest=match &h.arrays[id]{Array::Strings(v)=>v.clone(),_=>error("Path.of: se esperaba String[]")};
    let mut full=initial;for item in rest{let part=String::from_utf16(string_units(h,item)).unwrap_or_else(|_|error("Path.of: UTF-16 no representable"));if part.is_empty(){continue;}if !full.is_empty(){full.push('/');}full.push_str(&part);}
    if full.contains('\0'){error("Path.of: NUL no soportado");}
    let mut normalized=String::new();let mut slash=false;for c in full.chars(){if c=='/'{if !slash{normalized.push(c);}slash=true;}else{normalized.push(c);slash=false;}}if normalized.len()>1&&normalized.ends_with('/'){normalized.pop();}
    if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let out=h.arrays.len();h.arrays.push(Array::Path(normalized,None));out
}
fn path_text(h:&Heap,r:Option<usize>)->String{let id=array_id(h,r);match &h.arrays[id]{Array::Path(s,_)=>s.clone(),_=>error("Path concreto no soportado")}}
fn path_new(h:&mut Heap,text:String)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Path(text,None));id}
fn path_normalize_slashes(text:&str)->String{let mut normalized=String::new();let mut slash=false;for c in text.chars(){if c=='/'{if !slash{normalized.push(c);}slash=true;}else{normalized.push(c);slash=false;}}if normalized.len()>1&&normalized.ends_with('/'){normalized.pop();}normalized}
fn path_resolve(h:&mut Heap,r:Option<usize>,other:Option<usize>)->usize{let base=path_text(h,r);let part=String::from_utf16(string_units(h,other)).unwrap_or_else(|_|error("Path.resolve: UTF-16 no representable"));if part.contains('\0'){error("Path.resolve: NUL no soportado");}if part.is_empty(){return path_new(h,base);}let text=if part.starts_with('/')||base.is_empty(){part}else{format!("{base}/{part}")};path_new(h,path_normalize_slashes(&text))}
fn path_absolute(h:&mut Heap,r:Option<usize>)->usize{let p=path_text(h,r);if p.starts_with('/'){return array_id(h,r);}let cwd=std::env::current_dir().unwrap_or_else(|e|error(&format!("Path.toAbsolutePath: {e}")));let cwd=cwd.to_str().unwrap_or_else(||error("Path.toAbsolutePath: directorio no UTF-8"));let combined=if p.is_empty(){cwd.to_owned()}else{format!("{cwd}/{p}")};path_new(h,path_normalize_slashes(&combined))}
fn path_parent(h:&mut Heap,r:Option<usize>)->Option<usize>{let p=path_text(h,r);if p=="/"{return None;}let pos=p.rfind('/')?;let parent=if pos==0{"/"}else{&p[..pos]};Some(path_new(h,parent.to_owned()))}
fn file_new(h:&mut Heap)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::File(None,None));id}
fn file_init(h:&mut Heap,r:Option<usize>,s:Option<usize>){let id=array_id(h,r);let value=String::from_utf16(string_units(h,s)).unwrap_or_else(|_|error("File: UTF-16 no representable"));let value=path_normalize_slashes(&value);match &mut h.arrays[id]{Array::File(p,cache)=>{*p=Some(value);*cache=None},_=>error("File concreto no soportado")}}
fn file_to_path(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);let (text,cached)=match &h.arrays[id]{Array::File(Some(s),c)=>(s.clone(),*c),_=>error("File no inicializado")};if let Some(v)=cached{return v;}if text.contains('\0'){error("File.toPath: NUL no soportado");}let out=path_new(h,text);if let Array::File(_,c)=&mut h.arrays[id]{*c=Some(out);}out}
fn files_kind(h:&Heap,r:Option<usize>,options:Option<usize>,kind:&str)->bool{let p=path_text(h,r);let id=array_id(h,options);if !matches!(&h.arrays[id],Array::ProjectRefs("java/nio/file/LinkOption",v) if v.is_empty()){error("Files: solo opciones de enlace predeterminadas");}match std::fs::metadata(if p.is_empty(){"."}else{&p}){Ok(meta)=>match kind{"exists"=>true,"isDirectory"=>meta.is_dir(),"isRegularFile"=>meta.is_file(),_=>unreachable!()},Err(_)=>false}}
fn files_symbolic_link(h:&Heap,r:Option<usize>)->bool{{let p=path_text(h,r);std::fs::symlink_metadata(if p.is_empty(){"."}else{&p}).map(|m|m.file_type().is_symlink()).unwrap_or(false)}}
fn path_to_string(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);let (text,cached)=match &h.arrays[id]{Array::Path(s,c)=>(s.clone(),*c),_=>error("Path concreto no soportado")};if let Some(c)=cached{return c;}let value=new_string(h,text.encode_utf16().collect());if let Array::Path(_,c)=&mut h.arrays[id]{*c=Some(value);}value}
fn files_new_output(h:&mut Heap,path:Option<usize>,options:Option<usize>)->usize{let text=path_text(h,path);let o=array_id(h,options);if !matches!(&h.arrays[o],Array::ProjectRefs("java/nio/file/OpenOption",v) if v.is_empty()){error("Files.newOutputStream: opciones no soportadas");}let file=match std::fs::OpenOptions::new().write(true).create(true).truncate(true).open(if text.is_empty(){"."}else{&text}){Ok(f)=>f,Err(e)=>{let kind=match e.kind(){std::io::ErrorKind::NotFound=>"NoSuchFileException",std::io::ErrorKind::PermissionDenied=>"AccessDeniedException",_=>error(&format!("Files.newOutputStream: E/S no traducida: {e}"))};let msg=new_string(h,text.encode_utf16().collect());let ex=new_exception(h,kind);init_exception(h,Some(ex),kind,Some(msg));throw_ref(h,Some(ex));}};if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::FileOutput(Some(file)));id}
fn file_output_close(h:&mut Heap,r:Option<usize>){let id=array_id(h,r);match &mut h.arrays[id]{Array::FileOutput(file)=>{*file=None;},_=>error("OutputStream concreto no soportado")}}
fn files_new_input(h:&mut Heap,path:Option<usize>,options:Option<usize>)->usize{let text=path_text(h,path);let o=array_id(h,options);if !matches!(&h.arrays[o],Array::ProjectRefs("java/nio/file/OpenOption",v) if v.is_empty()){error("Files.newInputStream: opciones no soportadas");}let file=match std::fs::File::open(if text.is_empty(){"."}else{&text}){Ok(f)=>f,Err(e)=>{let kind=match e.kind(){std::io::ErrorKind::NotFound=>"NoSuchFileException",std::io::ErrorKind::PermissionDenied=>"AccessDeniedException",_=>error(&format!("Files.newInputStream: E/S no traducida: {e}"))};let msg=new_string(h,text.encode_utf16().collect());let ex=new_exception(h,kind);init_exception(h,Some(ex),kind,Some(msg));throw_ref(h,Some(ex));}};if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::FileInput(Some(file)));id}
fn files_write_string(h:&mut Heap,path:Option<usize>,text:Option<usize>,options:Option<usize>)->Option<usize>{
    let p=array_id(h,path);let content=array_id(h,text);let opts=array_id(h,options);
    let path_text=match &h.arrays[p]{Array::Path(s,_)=>s.clone(),_=>error("Files.writeString: Path concreto no soportado")};
    let units=match &h.arrays[content]{Array::Str(v)|Array::Builder(v)=>v.clone(),_=>error("Files.writeString: CharSequence no soportada")};
    if !matches!(&h.arrays[opts],Array::ProjectRefs("java/nio/file/OpenOption",v) if v.is_empty()){error("Files.writeString: solo opciones predeterminadas");}
    let data=String::from_utf16(&units).unwrap_or_else(|_|error("Files.writeString: UTF-16 no representable"));
    if let Err(e)=std::fs::write(if path_text.is_empty(){"."}else{&path_text},data.as_bytes()){
        let kind=match e.kind(){std::io::ErrorKind::NotFound=>"NoSuchFileException",std::io::ErrorKind::PermissionDenied=>"AccessDeniedException",_=>error(&format!("Files.writeString: error de E/S no traducido: {e}"))};
        let msg=new_string(h,path_text.encode_utf16().collect());let ex=new_exception(h,kind);init_exception(h,Some(ex),kind,Some(msg));throw_ref(h,Some(ex));
    }path
}
fn primitive_array_instance(h:&Heap,r:Option<usize>,name:&str)->bool{matches!((name,r.and_then(|id|h.arrays.get(id))),("[F",Some(Array::F(_)))|("[D",Some(Array::D(_)))|("[I",Some(Array::I(_)))|("[J",Some(Array::J(_)))|("[Z",Some(Array::Z(_)))|("[B",Some(Array::B(_)))|("[C",Some(Array::C(_)))|("[S",Some(Array::S(_))))}
fn charsequence_instance(h:&Heap,r:Option<usize>,interfaces:&[(&str,&str)])->bool{match r.and_then(|id|h.arrays.get(id)){Some(Array::Str(_)|Array::Builder(_))=>true,Some(Array::Obj(_,_)|Array::SharedObj(_,_)|Array::LocalObj(_,_,_)|Array::Exception(_,_,_))=>project_instance(h,r,"java/lang/CharSequence",interfaces),_=>false}}
fn charsequence_array_instance(h:&Heap,r:Option<usize>)->bool{match r.and_then(|id|h.arrays.get(id)){Some(Array::Strings(_))=>true,Some(Array::ProjectRefs("java/lang/CharSequence",_))=>true,Some(Array::ProjectRefs(actual,_)) if !actual.starts_with("java/")&&!actual.starts_with("javax/")=>error("cast covariante CharSequence[] no verificado"),_=>false}}
fn project_array_instance(h:&Heap,r:Option<usize>,class:&str)->bool{matches!(r.and_then(|id|h.arrays.get(id)),Some(Array::ProjectRefs(actual,_)) if *actual==class)}
fn array_id(h:&Heap,r:Option<usize>)->usize {let id=r.unwrap_or_else(||raise("NullPointerException",""));if id>=h.arrays.len(){panic!("referencia inválida");}id}
fn index(i:i32,n:usize)->usize {if i<0 || i as usize>=n {raise("ArrayIndexOutOfBoundsException","");}i as usize}
fn array_len(h:&Heap,r:Option<usize>)->i32 {h.arrays[array_id(h,r)].len() as i32}
fn reflect_array_length(h:&Heap,r:Option<usize>)->i32{let id=array_id(h,r);match &h.arrays[id]{Array::Z(_)|Array::B(_)|Array::C(_)|Array::S(_)|Array::I(_)|Array::J(_)|Array::F(_)|Array::D(_)|Array::Strings(_)|Array::Refs(_,_)|Array::ProjectRefs(_,_)=>h.arrays[id].len() as i32,_=>raise("IllegalArgumentException","")}}
// Copia temporal para respetar solapamiento; las referencias incompatibles
// fallan en el primer elemento, conservando las escrituras anteriores.
fn array_sort_char(h:&mut Heap,r:Option<usize>){let id=array_id(h,r);match &mut h.arrays[id]{Array::C(v)=>v.sort_unstable(),_=>error("Arrays.sort: char[] concreto no soportado")}}
fn array_fill_char(h:&mut Heap,r:Option<usize>,value:i32){let id=array_id(h,r);match &mut h.arrays[id]{Array::C(v)=>v.fill(value as u16),_=>error("Arrays.fill: char[] concreto no soportado")}}
fn system_arraycopy(h:&mut Heap,src:Option<usize>,sp:i32,dst:Option<usize>,dp:i32,n:i32){
    let a=array_id(h,src);let b=array_id(h,dst);
    let kind=|v:&Array|match v{Array::Z(_)=>4,Array::C(_)=>5,Array::F(_)=>6,Array::D(_)=>7,Array::B(_)=>8,Array::S(_)=>9,Array::I(_)=>10,Array::J(_)=>11,Array::Strings(_)|Array::Refs(_,_)|Array::ProjectRefs(_,_)=>12,_=>0};
    let (ak,bk)=(kind(&h.arrays[a]),kind(&h.arrays[b]));if ak==0||bk==0||((ak!=12||bk!=12)&&ak!=bk){raise("ArrayStoreException","");}
    let (al,bl)=(h.arrays[a].len(),h.arrays[b].len());if sp<0||dp<0||n<0||(sp as usize).checked_add(n as usize).map_or(true,|e|e>al)||(dp as usize).checked_add(n as usize).map_or(true,|e|e>bl){raise("ArrayIndexOutOfBoundsException","");}
    let (load,store)=match ak{4|8=>(0x33,0x54),5=>(0x34,0x55),6=>(0x30,0x51),7=>(0x31,0x52),9=>(0x35,0x56),10=>(0x2e,0x4f),11=>(0x2f,0x50),12=>(0x32,0x53),_=>unreachable!()};
    let values=(0..n).map(|i|array_load(h,Some(a),sp+i,load)).collect::<Vec<_>>();for (i,v) in values.into_iter().enumerate(){array_store(h,Some(b),dp+i as i32,v,store);}
}
fn array_load(h:&Heap,r:Option<usize>,i:i32,op:u8)->V {
    let a=&h.arrays[array_id(h,r)];let i=index(i,a.len());
    match (a,op) {
        (Array::I(v),0x2e)=>V::I(v[i]), (Array::J(v),0x2f)=>V::L(v[i]),(Array::F(v),0x30)=>V::F(v[i]),(Array::D(v),0x31)=>V::D(v[i]), (Array::Strings(v),0x32)=>V::R(v[i]), (Array::Refs(_,v),0x32)=>V::R(v[i]),(Array::ProjectRefs(_,v),0x32)=>V::R(v[i]),
        (Array::B(v),0x33)=>V::I(v[i] as i32), (Array::Z(v),0x33)=>V::I(i32::from(v[i])),
        (Array::C(v),0x34)=>V::I(v[i] as i32), (Array::S(v),0x35)=>V::I(v[i] as i32),
        _=>panic!("tipo de array incompatible para carga"),
    }
}
fn array_store(h:&mut Heap,r:Option<usize>,i:i32,val:V,op:u8) {
    let id=array_id(h,r);let i=index(i,h.arrays[id].len());
    if op==0x53 {if let V::R(Some(value_id))=val {
        let value=h.arrays.get(value_id).expect("referencia inválida");
        let compatible=match &h.arrays[id] {Array::Strings(_)=>matches!(value,Array::Str(_)),Array::Refs(13,_)=>true,Array::Refs(14,_)=>matches!(value,Array::Class(_)),Array::ProjectRefs("java/lang/Integer",_)=>matches!(value,Array::Integer(_)),Array::ProjectRefs("java/lang/Boolean",_)=>matches!(value,Array::Boolean(_)),Array::ProjectRefs("java/lang/Character",_)=>matches!(value,Array::Character(_)),Array::ProjectRefs("java/lang/Long",_)=>matches!(value,Array::Long(_)),Array::ProjectRefs("java/lang/Byte",_)=>matches!(value,Array::Byte(_)),Array::ProjectRefs("java/lang/Float",_)=>matches!(value,Array::Float(_)),Array::ProjectRefs("java/lang/ClassLoader",_)=>matches!(value,Array::AppLoader|Array::PlatformLoader),Array::ProjectRefs("java/lang/CharSequence",_)=>match value{Array::Str(_)|Array::Builder(_)=>true,Array::Obj(_,_)|Array::SharedObj(_,_)|Array::LocalObj(_,_,_)=>error("CharSequence[]: tipo proyecto no verificado"),_=>false},Array::ProjectRefs(class,_)=>project_instance(h,Some(value_id),class,h.interfaces),_=>false};
        if !compatible {raise("ArrayStoreException","");}
    }}
    let a=&mut h.arrays[id];
    match (a,op,val) {
        (Array::I(v),0x4f,V::I(x))=>v[i]=x, (Array::J(v),0x50,V::L(x))=>v[i]=x,(Array::F(v),0x51,V::F(x))=>v[i]=x,(Array::D(v),0x52,V::D(x))=>v[i]=x, (Array::Strings(v),0x53,V::R(x))=>v[i]=x, (Array::Refs(_,v),0x53,V::R(x))=>v[i]=x,(Array::ProjectRefs(_,v),0x53,V::R(x))=>v[i]=x,
        (Array::B(v),0x54,V::I(x))=>v[i]=x as i8, (Array::Z(v),0x54,V::I(x))=>v[i]=(x&1)!=0,
        (Array::C(v),0x55,V::I(x))=>v[i]=x as u16, (Array::S(v),0x56,V::I(x))=>v[i]=x as i16,
        _=>panic!("tipo de array incompatible para escritura"),
    }
}
fn parse_array(h:&mut Heap,text:&str,kind:char,prior:&[(char,Option<usize>)])->Option<usize> {
    if text=="null" {return None;}
    if let Some(a)=text.strip_prefix('@') {
        let n=a.parse::<usize>().unwrap_or_else(|_|error("Alias de array inválido"));
        let (old_kind,r)=*prior.get(n).unwrap_or_else(||error("Alias de array fuera de rango"));
        if r.is_some() && old_kind!=kind {error("Alias de array con tipo incompatible");}
        return r;
    }
    let s=text.strip_prefix('[').and_then(|x|x.strip_suffix(']')).unwrap_or_else(||error("Argumento array inválido: usa null o [1,2]"));
    let n=if s.trim().is_empty(){0}else{s.split(',').count()};
    if n>1_000_000 {error("Límite experimental de arrays excedido");}
    let k=match kind {'Z'=>4,'C'=>5,'B'=>8,'S'=>9,'I'=>10,'J'=>11,_=>panic!("tipo array inválido")};
    let id=array_new(h,k,n as i32);
    if n>0 {for (i,part) in s.split(',').enumerate() {
        let x=part.trim().parse::<i64>().unwrap_or_else(|_|error("Elemento de array inválido"));
        let (op,value)=match kind {
            'Z' if (0..=1).contains(&x)=>(0x54,V::I(x as i32)),
            'B' if (-128..=127).contains(&x)=>(0x54,V::I(x as i32)),
            'C' if (0..=65535).contains(&x)=>(0x55,V::I(x as i32)),
            'S' if (-32768..=32767).contains(&x)=>(0x56,V::I(x as i32)),
            'I' if (i32::MIN as i64..=i32::MAX as i64).contains(&x)=>(0x4f,V::I(x as i32)),
            'J'=>(0x50,V::L(x)),
            _=>error("Elemento de array fuera de rango Java"),
        };
        array_store(h,Some(id),i as i32,value,op);
    }}
    Some(id)
}

// String Java es una secuencia UTF-16, no bytes UTF-8 ni escalares Unicode.
fn new_string(h:&mut Heap,units:Vec<u16>)->usize {
    if h.arrays.len()>=10000 || h.elements.checked_add(units.len()).map_or(true,|v|v>1_000_000) {error("Límite experimental de heap excedido");}
    let id=h.arrays.len();h.elements+=units.len();h.arrays.push(Array::Str(units));id
}
fn string_literal(h:&mut Heap,units:&[u16])->usize {
    if let Some(id)=h.intern.get(units) {return *id;}
    let id=new_string(h,units.to_vec());h.intern.insert(units.to_vec(),id);id
}
fn string_to_char_array(h:&mut Heap,r:Option<usize>)->usize{let units=string_units(h,r).to_vec();if h.arrays.len()>=10000||h.elements.checked_add(units.len()).map_or(true,|n|n>1_000_000){error("String.toCharArray: límite experimental de arrays excedido");}let id=h.arrays.len();h.elements+=units.len();h.arrays.push(Array::C(units));id}
fn string_units(h:&Heap,r:Option<usize>)->&[u16] {
    let id=array_id(h,r);match &h.arrays[id] {Array::Str(v)=>v,_=>panic!("se esperaba String")}
}
fn builder_new(h:&mut Heap)->usize {if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Builder(Vec::new()));h.builder_caps.insert(id,(16,false));id}
fn builder_init_capacity(h:&mut Heap,r:Option<usize>,capacity:i32){let _=builder_id(h,r);if capacity<0{let msg=new_string(h,capacity.to_string().encode_utf16().collect());let ex=new_exception(h,"NegativeArraySizeException");init_exception(h,Some(ex),"NegativeArraySizeException",Some(msg));throw_ref(h,Some(ex));}if capacity>1_000_000{error("StringBuilder(int): capacidad fuera del perfil");}let id=builder_id(h,r);h.builder_caps.insert(id,(capacity,false));}
fn builder_id(h:&Heap,r:Option<usize>)->usize {let id=array_id(h,r);if !matches!(h.arrays[id],Array::Builder(_)){panic!("se esperaba StringBuilder");}id}
fn builder_init_string(h:&mut Heap,r:Option<usize>,s:Option<usize>){let id=builder_id(h,r);let units=string_units(h,s).to_vec();let capacity=i32::try_from(units.len()).ok().and_then(|v|v.checked_add(16)).unwrap_or_else(||error("StringBuilder(String): capacidad fuera del perfil"));h.builder_caps.insert(id,(capacity,false));builder_append(h,r,&units);}
fn builder_capacity(h:&Heap,r:Option<usize>)->i32{let id=builder_id(h,r);h.builder_caps.get(&id).expect("capacidad StringBuilder ausente").0}
fn builder_grow(h:&mut Heap,id:usize,needed:usize,widen:bool){let (old,utf)=*h.builder_caps.get(&id).expect("capacidad StringBuilder ausente");let old=old as usize;let next=if needed>old{if widen&&!utf{old.saturating_add(2).max(needed)}else{old.saturating_mul(2).saturating_add(2).max(needed)}}else{old};if next>2_000_002{error("StringBuilder: capacidad fuera del perfil");}h.builder_caps.insert(id,(next as i32,utf||widen));}
fn builder_set_length(h:&mut Heap,r:Option<usize>,n:i32){let id=builder_id(h,r);if n<0{let msg=new_string(h,format!("String index out of range: {n}").encode_utf16().collect());let ex=new_exception(h,"StringIndexOutOfBoundsException");init_exception(h,Some(ex),"StringIndexOutOfBoundsException",Some(msg));throw_ref(h,Some(ex));}let old=match &h.arrays[id]{Array::Builder(v)=>v.len(),_=>unreachable!()};let n=n as usize;if n>1_000_000{error("StringBuilder.setLength: longitud fuera del perfil");}if n>old{let delta=n-old;if h.elements.saturating_add(delta)>1_000_000{error("Límite experimental de cadenas excedido");}builder_grow(h,id,n,false);if let Array::Builder(v)=&mut h.arrays[id]{v.resize(n,0);}h.elements+=delta;}else if let Array::Builder(v)=&mut h.arrays[id]{v.truncate(n);}}
fn builder_trim(h:&mut Heap,r:Option<usize>){let id=builder_id(h,r);let len=match &h.arrays[id]{Array::Builder(v)=>v.len(),_=>unreachable!()};let utf=h.builder_caps.get(&id).expect("capacidad StringBuilder ausente").1;h.builder_caps.insert(id,(len as i32,utf));}
fn builder_append(h:&mut Heap,r:Option<usize>,units:&[u16])->Option<usize> {builder_append_coder(h,r,units,units.iter().any(|c|*c>255))}
fn builder_append_coder(h:&mut Heap,r:Option<usize>,units:&[u16],wide:bool)->Option<usize>{let id=builder_id(h,r);if h.elements.checked_add(units.len()).map_or(true,|v|v>1_000_000){error("Límite experimental de cadenas excedido");}let len=match &h.arrays[id]{Array::Builder(v)=>v.len(),_=>unreachable!()};builder_grow(h,id,len.saturating_add(units.len()),wide);if let Array::Builder(ref mut b)=h.arrays[id]{b.extend_from_slice(units);}h.elements+=units.len();Some(id)}
fn builder_append_string(h:&mut Heap,r:Option<usize>,s:Option<usize>)->Option<usize>{
    builder_id(h,r);let units=match s {None=>vec![110,117,108,108],Some(_)=>string_units(h,s).to_vec()};builder_append(h,r,&units)
}
fn builder_append_charsequence(h:&mut Heap,r:Option<usize>,s:Option<usize>)->Option<usize>{builder_id(h,r);let (units,wide)=match s{None=>(vec![110,117,108,108],false),Some(id)=>match &h.arrays[id]{Array::Str(v)=>(v.clone(),v.iter().any(|c|*c>255)),Array::Builder(v)=>(v.clone(),h.builder_caps.get(&id).expect("capacidad StringBuilder ausente").1),_=>error("StringBuilder.append(CharSequence): receptor fuera del perfil")}};builder_append_coder(h,r,&units,wide)}
// append(CharSequence,start,end) crece antes de ensanchar el coder, como Java 25.
fn builder_append_charsequence_range(h:&mut Heap,r:Option<usize>,s:Option<usize>,start:i32,end:i32)->Option<usize>{let id=builder_id(h,r);let units=match s{None=>vec![110,117,108,108],Some(src)=>match &h.arrays[src]{Array::Str(v)|Array::Builder(v)=>v.clone(),_=>error("StringBuilder.append(CharSequence,int,int): fuente fuera del perfil")}};let len=units.len();if start<0||end<start||end as usize>len{let text=new_string(h,format!("Range [{start}, {end}) out of bounds for length {len}").encode_utf16().collect());let ex=new_exception(h,"IndexOutOfBoundsException");init_exception(h,Some(ex),"IndexOutOfBoundsException",Some(text));throw_ref(h,Some(ex));}let selected=&units[start as usize..end as usize];let oldlen=match &h.arrays[id]{Array::Builder(v)=>v.len(),_=>unreachable!()};if h.elements.checked_add(selected.len()).map_or(true,|v|v>1_000_000){error("Límite experimental de cadenas excedido");}builder_grow(h,id,oldlen.saturating_add(selected.len()),false);builder_append(h,r,selected)}
fn builder_append_object(h:&mut Heap,r:Option<usize>,v:Option<usize>)->Option<usize> {
    builder_id(h,r);if let Some(id)=v {if !matches!(h.arrays.get(id),Some(Array::Str(_))){error("StringBuilder.append(Object): toString de objeto no soportado");}}
    builder_append_string(h,r,v)
}
fn builder_len(h:&Heap,r:Option<usize>)->i32 {let id=builder_id(h,r);match &h.arrays[id]{Array::Builder(v)=>v.len() as i32,_=>unreachable!()}}
fn builder_to_string(h:&mut Heap,r:Option<usize>)->usize{let id=builder_id(h,r);let v=match &h.arrays[id]{Array::Builder(v)=>v.clone(),_=>unreachable!()};if v.is_empty(){string_literal(h,&[])}else{new_string(h,v)}}
// Solo conversiones que no requieren Formatter general ni Object.toString.
// Cualquier formato/argumento fuera del subconjunto aborta explícitamente.
fn string_format_basic(h:&mut Heap,fmt:Option<usize>,args:Option<usize>)->usize {
    let format=string_units(h,fmt).to_vec();
    let values=match args {None=>None,Some(id)=>Some(match h.arrays.get(id) {Some(Array::Strings(v))|Some(Array::Refs(_,v))|Some(Array::ProjectRefs(_,v))=>v.clone(),_=>panic!("se esperaba Object[]")})};
    let mut out=Vec::new();let mut i=0;let mut arg=0;
    while i<format.len() {
        let c=format[i];i+=1;
        if c!=b'%' as u16 {out.push(c);} else {
            if i==format.len(){error("String.format: formato no soportado");}let conv=format[i];i+=1;
            match conv {
                x if x==b'%' as u16=>out.push(b'%' as u16),
                x if x==b'n' as u16=>{if cfg!(windows){out.push(13);}out.push(10);},
                x if x==b's' as u16=>{
                    let value=match &values {None=>None,Some(v)=>*v.get(arg).unwrap_or_else(||error("String.format: argumento ausente no soportado"))};arg+=1;
                    match value {None=>out.extend([110,117,108,108]),Some(id)=>match h.arrays.get(id){Some(Array::Str(v))=>out.extend(v),_=>error("String.format: %s con objeto no String no soportado")}}
                },
                _=>error("String.format: conversión no soportada"),
            }
        }
        if h.elements.checked_add(out.len()).map_or(true,|n|n>1_000_000){error("Límite experimental de cadenas excedido");}
    }
    new_string(h,out)
}
fn string_hash(h:&Heap,r:Option<usize>)->i32{let mut n=0i32;for c in string_units(h,r){n=n.wrapping_mul(31).wrapping_add(*c as i32);}n}
fn string_len(h:&Heap,r:Option<usize>)->i32 {string_units(h,r).len() as i32}
fn string_substring(h:&mut Heap,r:Option<usize>,begin:i32,end:Option<i32>)->usize{let id=array_id(h,r);let units=string_units(h,Some(id));let end=end.unwrap_or(units.len() as i32);if begin<0||end<begin||end as usize>units.len(){raise("StringIndexOutOfBoundsException","");}if begin==0&&end as usize==units.len(){return id;}if begin==end{return string_literal(h,&[]);}let v=units[begin as usize..end as usize].to_vec();new_string(h,v)}
fn string_char_at(h:&Heap,r:Option<usize>,i:i32)->i32 {
    let a=string_units(h,r);if i<0 || i as usize>=a.len(){raise("StringIndexOutOfBoundsException","");}a[i as usize] as i32
}
fn string_equals(h:&Heap,a:Option<usize>,b:Option<usize>)->bool {
    let lhs=string_units(h,a);match b.and_then(|id|h.arrays.get(id)) {Some(Array::Str(rhs))=>lhs==rhs,_=>false}
}
fn string_starts(h:&Heap,a:Option<usize>,b:Option<usize>)->bool {string_units(h,a).starts_with(string_units(h,b))}
fn string_ends(h:&Heap,a:Option<usize>,b:Option<usize>)->bool {string_units(h,a).ends_with(string_units(h,b))}
fn string_index_char(h:&Heap,a:Option<usize>,c:i32,from:i32)->i32 {
    let hay=string_units(h,a);let start=from.max(0) as usize;
    let needle:Vec<u16>=if (0..=0xffff).contains(&c) {vec![c as u16]} else if (0x10000..=0x10ffff).contains(&c) {let n=(c-0x10000) as u32;vec![(0xd800+(n>>10)) as u16,(0xdc00+(n&1023)) as u16]} else {return -1};
    if start>=hay.len() {return -1;}
    hay[start..].windows(needle.len()).position(|x|x==needle).map_or(-1,|i|(i+start) as i32)
}
fn string_index_str(h:&Heap,a:Option<usize>,b:Option<usize>,from:i32)->i32 {
    let hay=string_units(h,a);let needle=string_units(h,b);let start=(from.max(0) as usize).min(hay.len());
    if needle.is_empty(){return start as i32;}
    if from as i64>hay.len() as i64 || needle.len()>hay.len().saturating_sub(start){return -1;}
    hay[start..].windows(needle.len()).position(|x|x==needle).map_or(-1,|i|(i+start) as i32)
}
fn string_split_version(h:&mut Heap,r:Option<usize>,pattern:Option<usize>,limit:i32)->usize{let id=array_id(h,r);let input=string_units(h,r).to_vec();let regex=string_units(h,pattern);if !regex.iter().copied().eq(r"-|\.".encode_utf16())||limit!=3{error("String.split: solo patrón y límite de versión Log4j");}let mut spans=Vec::new();let mut start=0;for (pos,c) in input.iter().enumerate(){if (*c==45||*c==46)&&spans.len()<2{spans.push((start,pos));start=pos+1;}}let out=if spans.is_empty(){vec![Some(id)]}else{spans.push((start,input.len()));let mut v=Vec::with_capacity(spans.len());for (a,b) in spans{let part=if a==b{string_literal(h,&[])}else{new_string(h,input[a..b].to_vec())};v.push(Some(part));}v};if h.arrays.len()>=10000||h.elements.saturating_add(out.len())>1_000_000{error("Límite experimental de heap excedido");}h.elements+=out.len();let result=h.arrays.len();h.arrays.push(Array::Strings(out));result}
fn string_contains_sequence(h:&Heap,r:Option<usize>,seq:Option<usize>)->bool{let hay=string_units(h,r);let id=array_id(h,seq);let needle=match &h.arrays[id]{Array::Str(v)|Array::Builder(v)=>v,_=>error("String.contains: CharSequence fuera del perfil")};needle.is_empty()||(needle.len()<=hay.len()&&hay.windows(needle.len()).any(|v|v==needle))}
fn string_last_index_str(h:&Heap,a:Option<usize>,b:Option<usize>)->i32{let hay=string_units(h,a);let needle=string_units(h,b);if needle.is_empty(){return hay.len() as i32;}if needle.len()>hay.len(){return -1;}hay.windows(needle.len()).rposition(|x|x==needle).map_or(-1,|i|i as i32)}
fn character_whitespace_char(v:i32)->bool{let c=v as u16;WHITESPACE_CHAR_JAVA25.iter().any(|(lo,hi)|*lo<=c&&c<=*hi)}
fn character_upper_char(v:i32)->i32{let c=v as u16;match UPPER_CHAR_JAVA25.binary_search_by_key(&c,|e|e.0){Ok(i)=>UPPER_CHAR_JAVA25[i].1 as i32,Err(_)=>c as i32}}
fn box_character(h:&mut Heap,v:i32)->usize{let c=v as u16;if c<=127{if let Some(id)=h.characters.get(&c){return *id;}}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Character(c));if c<=127{h.characters.insert(c,id);}id}
fn unbox_character(h:&Heap,r:Option<usize>)->i32{let id=array_id(h,r);match h.arrays[id]{Array::Character(c)=>c as i32,_=>error("Character concreto no soportado")}}
fn string_init_chars(h:&mut Heap,r:Option<usize>,chars:Option<usize>){let id=array_id(h,r);let cid=array_id(h,chars);let v=match &h.arrays[cid]{Array::C(v)=>v.clone(),_=>error("String(char[]): argumento no soportado")};if h.elements.checked_add(v.len()).map_or(true,|n|n>1_000_000){error("Límite experimental de heap excedido");}h.elements+=v.len();match &mut h.arrays[id]{Array::Str(s)=>*s=v,_=>error("String constructor inválido")}}
fn string_get_chars(h:&mut Heap,r:Option<usize>,begin:i32,end:i32,dst:Option<usize>,off:i32){let s=string_units(h,r);if begin<0||end<begin||end as usize>s.len(){raise("StringIndexOutOfBoundsException","");}let v=s[begin as usize..end as usize].to_vec();let id=array_id(h,dst);let d=match &mut h.arrays[id]{Array::C(d)=>d,_=>error("String.getChars: destino no char[]")};if off<0||(off as usize).saturating_add(v.len())>d.len(){raise("StringIndexOutOfBoundsException","");}d[off as usize..off as usize+v.len()].copy_from_slice(&v);}
fn object_equals_guard(h:&Heap,r:Option<usize>,other:Option<usize>)->bool{let id=array_id(h,r);match h.arrays[id]{Array::Class(_)=>Some(id)==other,Array::Str(_)=>string_equals(h,r,other),_=>error("Object.equals: receptor fuera del perfil")}}
fn objects_to_string_default(h:&mut Heap,r:Option<usize>,default:Option<usize>)->Option<usize>{match r{None=>default,Some(id)=>match h.arrays[id]{Array::Str(_)=>Some(id),Array::Builder(_)=>Some(builder_to_string(h,r)),_=>error("Objects.toString: receptor fuera del perfil")}}}
fn object_to_string_guard(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);match h.arrays[id]{Array::Str(_)=>id,_=>error("Object.toString: receptor fuera del perfil soportado")}}
fn character_to_string(h:&mut Heap,code:i32)->usize{if !(0..=0x10ffff).contains(&code){raise("IllegalArgumentException","");}let units=if code<=0xffff{vec![code as u16]}else{let c=(code-0x10000) as u32;vec![(0xd800+(c>>10)) as u16,(0xdc00+(c&1023)) as u16]};new_string(h,units)}
fn string_render(h:&Heap,r:Option<usize>)->String {
    match r {None=>"null".into(),Some(_)=>std::char::decode_utf16(string_units(h,r).iter().copied()).map(|x|x.unwrap_or('?')).collect()}
}
fn parse_string(h:&mut Heap,text:&str)->Option<usize> {
    if text=="null" {return None;}
    let content=text.strip_prefix("s:").unwrap_or_else(||error("String inválido: usa null o s:contenido"));
    Some(new_string(h,content.encode_utf16().collect()))
}
fn stdout_ref(h:&mut Heap)->usize {
    if let Some(id)=h.stdout {return id;}
    if h.arrays.len()>=10000 {error("Límite experimental de heap excedido");}
    let id=h.arrays.len();h.arrays.push(Array::Stdout);h.stdout=Some(id);id
}
fn stderr_ref(h:&mut Heap)->usize {
    if let Some(id)=h.stderr{return id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}
    let id=h.arrays.len();h.arrays.push(Array::Stderr);h.stderr=Some(id);id
}
fn print_line(h:&Heap,out:Option<usize>,text:&str){let id=array_id(h,out);match h.arrays[id] {Array::Stdout=>println!("{}",text),Array::Stderr=>eprintln!("{}",text),_=>panic!("se esperaba PrintStream del sistema")}}
fn print_string_line(h:&Heap,out:Option<usize>,s:Option<usize>){print_line(h,out,&string_render(h,s));}
fn argv_array(h:&mut Heap,args:&[String])->usize {
    let n=i32::try_from(args.len()).unwrap_or_else(|_|error("Límite experimental de heap excedido"));
    let id=array_new(h,12,n);
    for (i,v) in args.iter().enumerate() {let s=new_string(h,v.encode_utf16().collect());array_store(h,Some(id),i as i32,V::R(Some(s)),0x53);}
    id
}
fn parse_string_array(h:&mut Heap,text:&str,prior:&[(char,Option<usize>)])->Option<usize> {
    if text=="null" {return None;}
    if let Some(a)=text.strip_prefix('@') {
        let n=a.parse::<usize>().unwrap_or_else(|_|error("Alias de array inválido"));
        let (kind,r)=*prior.get(n).unwrap_or_else(||error("Alias de array fuera de rango"));
        if r.is_some() && kind!='T' {error("Alias de array con tipo incompatible");}return r;
    }
    let inside=text.strip_prefix("sarr:[").and_then(|v|v.strip_suffix(']')).unwrap_or_else(||error("String[] inválido"));
    let parts=if inside.is_empty(){Vec::new()} else {inside.split(',').collect::<Vec<_>>()};
    if parts.len()>1_000_000 {error("Límite experimental de heap excedido");}
    let id=array_new(h,12,parts.len() as i32);
    for (i,p) in parts.iter().enumerate() {
        let val=if *p=="n" {None} else {
            let hex=p.strip_prefix('x').unwrap_or_else(||error("String[] elemento inválido"));
            if hex.len()%2!=0 || !hex.is_ascii(){error("String[] hex inválido");}
            let mut bytes=Vec::new();for j in (0..hex.len()).step_by(2) {bytes.push(u8::from_str_radix(&hex[j..j+2],16).unwrap_or_else(|_|error("String[] hex inválido")));}
            let text=std::str::from_utf8(&bytes).unwrap_or_else(|_|error("String[] UTF-8 inválido"));
            Some(new_string(h,text.encode_utf16().collect()))
        };
        array_store(h,Some(id),i as i32,V::R(val),0x53);
    }
    Some(id)
}

fn builtin_instance(h:&Heap,r:Option<usize>,kind:&str)->bool {
    if matches!(kind,"map"|"concurrentmap"|"number"|"list"|"stream"|"stackframe")&&matches!(r.and_then(|id|h.arrays.get(id)),Some(Array::Obj(_,_)|Array::SharedObj(_,_)|Array::LocalObj(_,_,_))){error("Map/Number/List: objeto proyecto no verificado");}
    match (kind,r.and_then(|id|h.arrays.get(id))) {("list",Some(Array::List(_,_)|Array::ArraysList(_)|Array::ImmutableList(_)|Array::EmptyList))|("number",Some(Array::Byte(_)|Array::Short(_)|Array::Integer(_)|Array::Long(_)|Array::Float(_)|Array::Double(_)))|("stream",Some(Array::LazyStream(_,_,_,_)|Array::SortedStream(_,_,_)|Array::MappedStream(_,_,_)|Array::StackWalkStream(_,_,_,_,_)|Array::StackStage(_,_,_,_)))|("stackframe",Some(Array::StackFrame(_,_)))|("concurrentmap",Some(Array::Map(_,_,_)))|("map",Some(Array::Map(_,_,_)|Array::HashMap(_)|Array::IdentityMap(_)|Array::LinkedMap(_,_)|Array::TreeMap(_,_)|Array::EmptyMap))|("completedfuture",Some(Array::CompletedFuture(_)))|("optional",Some(Array::Optional(_)))|("class",Some(Array::Class(_)))|("classloader",Some(Array::AppLoader|Array::PlatformLoader))|("printstream",Some(Array::Stdout|Array::Stderr))|("builder",Some(Array::Builder(_)))|("reader",Some(Array::Reader(_,_,_,_)))|("inputstream",Some(Array::ResourceStream(_,_,_)|Array::FileInput(_)|Array::ByteInput(_,_,_,_)))|("uuid",Some(Array::Uuid(_)))|("uri",Some(Array::Uri(_)))|("pattern",Some(Array::Pattern(_,_)))|("long",Some(Array::Long(_)))|("float",Some(Array::Float(_)))|("double",Some(Array::Double(_)))|("byte",Some(Array::Byte(_)))|("short",Some(Array::Short(_)))|("character",Some(Array::Character(_)))|("integer",Some(Array::Integer(_)))|("boolean",Some(Array::Boolean(_)))|("s",Some(Array::Str(_)))|("t",Some(Array::Strings(_)))|("o",Some(_))|("A",Some(Array::Strings(_)))|("A",Some(Array::Refs(_, _)))|("A",Some(Array::ProjectRefs(_, _)))|("C",Some(Array::Refs(14,_)))=>true,_=>false}
}
fn serializable_instance(h:&Heap,r:Option<usize>,interfaces:&[(&str,&str)])->bool{let Some(id)=r else{return false};if h.enum_values.contains_key(&id){return true;}match h.arrays.get(id){
 Some(Array::Obj(_,_)|Array::SharedObj(_,_)|Array::LocalObj(_,_,_)|Array::Lambda(_,_,_)|Array::IdentityFunction)=>project_instance(h,r,"java/io/Serializable",interfaces),
 Some(Array::Str(_)|Array::Boolean(_)|Array::Integer(_)|Array::Long(_)|Array::Byte(_)|Array::Short(_)|Array::Character(_)|Array::Float(_)|Array::Double(_)|Array::Pattern(_,_)|Array::Uuid(_)|Array::Date(_)|Array::Class(_)|Array::Exception(_,_,_)|Array::I(_)|Array::J(_)|Array::F(_)|Array::D(_)|Array::Z(_)|Array::B(_)|Array::C(_)|Array::S(_)|Array::Strings(_)|Array::Refs(_,_)|Array::ProjectRefs(_,_)|Array::Map(_,_,_)|Array::HashMap(_)|Array::IdentityMap(_)|Array::IdentitySet(_)|Array::LinkedMap(_,_)|Array::TreeMap(_,_)|Array::EmptyMap|Array::EnumSet(_)|Array::EmptyList|Array::EmptySet|Array::ImmutableList(_)|Array::Queue(_)|Array::ConcurrentQueue(_)|Array::Deque(_)|Array::List(_,_)|Array::Set(_,_)|Array::HashSet(_,_))=>true,
 Some(Array::Local(_)|Array::SuppliedLocal(_,_)|Array::IsoInstantFormatter|Array::Optional(_))=>false,
 Some(_)=>error("Serializable: tipo JDK no inspeccionado"),None=>panic!("referencia inválida")}}
fn project_subtype(h:&Heap,mut actual:&str,target:&str)->bool{loop{if actual==target{return true;}match h.parents.get(actual){Some(parent)=>actual=parent,None=>return false}}}
fn utf8_charset(h:&mut Heap)->usize{if let Some(id)=h.utf8_charset{return id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Utf8Charset);h.utf8_charset=Some(id);id}
fn reader_new(h:&mut Heap)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Reader(None,None,0,false));id}
fn reader_init(h:&mut Heap,r:Option<usize>,stream:Option<usize>,charset:Option<usize>){let rid=array_id(h,r);let sid=array_id(h,stream);let cid=array_id(h,charset);if !matches!(h.arrays[cid],Array::Utf8Charset)||!matches!(h.arrays[sid],Array::ResourceStream(_,_,_)){error("InputStreamReader: solo recurso y UTF-8 verificados");}match &mut h.arrays[rid]{Array::Reader(source,_,_,_)=>*source=Some(sid),_=>error("InputStreamReader inválido")}}
fn reader_ready(h:&mut Heap,id:usize){let stream=match &h.arrays[id]{Array::Reader(Some(s),None,_,false)=>*s,Array::Reader(_,_,_,true)=>raise("IOException","Stream closed"),Array::Reader(_,Some(_),_,false)=>return,_=>error("InputStreamReader no inicializado")};let (bytes,pos)=match &h.arrays[stream]{Array::ResourceStream(bytes,pos,false)=>(*bytes,*pos),Array::ResourceStream(_,_,true)=>raise("IOException","Stream closed"),_=>unreachable!()};if bytes.len().saturating_sub(pos)>8192{error("InputStreamReader: recurso mayor al buffer verificado");}let text=std::str::from_utf8(&bytes[pos..]).unwrap_or_else(|_|error("InputStreamReader: UTF-8 inválido no soportado"));let units:Vec<u16>=text.encode_utf16().collect();if h.elements.saturating_add(units.len())>1_000_000{error("Límite experimental de heap excedido");}h.elements+=units.len();if let Array::ResourceStream(_,p,_)=&mut h.arrays[stream]{*p=bytes.len();}if let Array::Reader(_,buffer,_,_)=&mut h.arrays[id]{*buffer=Some(units);}}
fn reader_read(h:&mut Heap,r:Option<usize>)->i32{let id=array_id(h,r);reader_ready(h,id);match &mut h.arrays[id]{Array::Reader(_,Some(v),pos,false)=>{if *pos==v.len(){return -1;}let c=v[*pos];*pos+=1;c as i32},_=>unreachable!()}}
fn reader_read_chars(h:&mut Heap,r:Option<usize>,dst:Option<usize>,off:i32,len:i32)->i32{let id=array_id(h,r);if matches!(h.arrays[id],Array::Reader(_,_,_,true)){raise("IOException","Stream closed");}let a=array_id(h,dst);let size=match &h.arrays[a]{Array::C(v)=>v.len(),_=>error("Reader.read: destino no es char[]")};if off<0||len<0||(off as usize).saturating_add(len as usize)>size{raise("IndexOutOfBoundsException","");}if len==0{return 0;}reader_ready(h,id);let mut n=0;while n<len{let c=reader_read(h,r);if c<0{break;}array_store(h,dst,off+n,V::I(c),0x55);n+=1;}if n==0{-1}else{n}}
fn reader_close(h:&mut Heap,r:Option<usize>){let id=array_id(h,r);let stream=match &mut h.arrays[id]{Array::Reader(Some(s),_,_,closed)=>{*closed=true;*s},_=>error("InputStreamReader inválido")};resource_close(h,Some(stream));}
fn version_stream(h:&mut Heap,class:Option<usize>,name:Option<usize>,bytes:Option<&'static [u8]>)->Option<usize>{let id=array_id(h,class);let class=match h.arrays[id]{Array::Class(c)=>c,_=>panic!("se esperaba Class")};let n=string_units(h,name);let expected:Vec<u16>="/version.json".encode_utf16().collect();if class!="net/minecraft/DetectedVersion"||n!=expected{error("Class.getResourceAsStream: recurso fuera del perfil verificado");}let bytes=bytes?;if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::ResourceStream(bytes,0,false));Some(id)}
fn byte_input_new(h:&mut Heap)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::ByteInput(None,0,0,0));id}
fn byte_input_init(h:&mut Heap,r:Option<usize>,buffer:Option<usize>){let id=array_id(h,r);let buf=array_id(h,buffer);let len=match &h.arrays[buf]{Array::B(v)=>v.len(),_=>error("ByteArrayInputStream: se requiere byte[]")};match &mut h.arrays[id]{Array::ByteInput(b,p,m,c)=>{*b=Some(buf);*p=0;*m=0;*c=len},_=>error("ByteArrayInputStream: receptor fuera del perfil")}}
fn byte_input_read(h:&mut Heap,id:usize)->i32{let (buf,pos,count)=match h.arrays[id]{Array::ByteInput(Some(buf),p,_,c)=>(buf,p,c),_=>error("ByteArrayInputStream no inicializado")};if pos>=count{return -1;}let value=match &h.arrays[buf]{Array::B(v)=>v[pos] as u8 as i32,_=>unreachable!()};if let Array::ByteInput(_,p,_,_)=&mut h.arrays[id]{*p+=1;}value}
fn byte_input_read_range(h:&mut Heap,r:Option<usize>,dest:Option<usize>,off:i32,len:i32)->i32{let id=array_id(h,r);let dst=array_id(h,dest);let size=match &h.arrays[dst]{Array::B(v)=>v.len(),_=>error("ByteArrayInputStream.read: destino no byte[]")};if off<0||len<0||(off as usize).checked_add(len as usize).map_or(true,|n|n>size){let text=new_string(h,format!("Range [{off}, {off} + {len}) out of bounds for length {size}").encode_utf16().collect());let ex=new_exception(h,"IndexOutOfBoundsException");init_exception(h,Some(ex),"IndexOutOfBoundsException",Some(text));throw_ref(h,Some(ex));}let (buf,pos,count)=match h.arrays[id]{Array::ByteInput(Some(b),p,_,c)=>(b,p,c),_=>error("InputStream.read(byte[],int,int): solo ByteArrayInputStream soportado")};if pos>=count{return -1;}let n=(len as usize).min(count-pos);if n==0{return 0;}let bytes=match &h.arrays[buf]{Array::B(v)=>v[pos..pos+n].to_vec(),_=>unreachable!()};if let Array::B(v)=&mut h.arrays[dst]{v[off as usize..off as usize+n].copy_from_slice(&bytes);}if let Array::ByteInput(_,p,_,_)=&mut h.arrays[id]{*p+=n;}n as i32}
fn byte_input_available(h:&Heap,r:Option<usize>)->i32{let id=array_id(h,r);match h.arrays[id]{Array::ByteInput(Some(_),p,_,c)=>(c-p) as i32,_=>error("InputStream.available: solo ByteArrayInputStream soportado")}}
fn byte_input_skip(h:&mut Heap,r:Option<usize>,n:i64)->i64{let id=array_id(h,r);let (p,c)=match h.arrays[id]{Array::ByteInput(Some(_),p,_,c)=>(p,c),_=>error("InputStream.skip: solo ByteArrayInputStream soportado")};let amount=n.max(0).min((c-p) as i64) as usize;if let Array::ByteInput(_,pos,_,_)=&mut h.arrays[id]{*pos+=amount;}amount as i64}
fn byte_input_mark(h:&mut Heap,r:Option<usize>){let id=array_id(h,r);match &mut h.arrays[id]{Array::ByteInput(Some(_),p,mark,_)=>*mark=*p,_=>error("InputStream.mark: solo ByteArrayInputStream soportado")}}
fn byte_input_reset(h:&mut Heap,r:Option<usize>){let id=array_id(h,r);match &mut h.arrays[id]{Array::ByteInput(Some(_),p,mark,_)=>*p=*mark,_=>error("InputStream.reset: solo ByteArrayInputStream soportado")}}
fn resource_read(h:&mut Heap,r:Option<usize>)->i32{let id=array_id(h,r);if matches!(h.arrays[id],Array::ByteInput(_,_,_,_)){return byte_input_read(h,id);}match &mut h.arrays[id]{Array::ResourceStream(bytes,pos,closed)=>{if *closed{raise("IOException","Stream closed");}if *pos>=bytes.len(){return -1;}let b=bytes[*pos];*pos+=1;b as i32},Array::FileInput(file)=>{use std::io::Read;let file=file.as_mut().unwrap_or_else(||raise("IOException","Stream Closed"));let mut b=[0u8;1];match file.read(&mut b){Ok(0)=>-1,Ok(_)=>b[0] as i32,Err(e)=>error(&format!("InputStream.read: E/S no traducida: {e}"))}},_=>error("InputStream concreto no soportado")}}
fn resource_close(h:&mut Heap,r:Option<usize>){let id=array_id(h,r);if matches!(h.arrays[id],Array::ByteInput(_,_,_,_)){return;}match &mut h.arrays[id]{Array::ResourceStream(_,_,closed)=>*closed=true,Array::FileInput(file)=>{*file=None;},_=>error("InputStream concreto no soportado")}}
fn collectors_joining(h:&mut Heap,delimiter:Option<usize>,prefix:Option<usize>,suffix:Option<usize>)->usize {for v in [delimiter,prefix,suffix].into_iter().flatten(){if !matches!(h.arrays[v],Array::Str(_)){error("Collectors.joining: solo String/null soportados");}}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::JoinCollector(delimiter,prefix,suffix));id}
fn current_time_millis()->i64{let millis=match std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH){Ok(v)=>i128::try_from(v.as_millis()).unwrap_or_else(|_|error("System.currentTimeMillis: reloj fuera de rango")),Err(e)=>-i128::try_from((e.duration().as_nanos()+999_999)/1_000_000).unwrap_or_else(|_|error("System.currentTimeMillis: reloj fuera de rango"))};i64::try_from(millis).unwrap_or_else(|_|error("System.currentTimeMillis: reloj fuera de rango"))}
fn current_thread(h:&mut Heap)->usize{if let Some(id)=h.arrays.iter().position(|a|matches!(a,Array::CurrentThread(_,_))){return id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let name=new_string(h,vec![109,97,105,110]);if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::CurrentThread(false,name));id}
fn thread_is_interrupted(h:&Heap,r:Option<usize>)->bool{let id=array_id(h,r);match h.arrays[id]{Array::CurrentThread(flag,_)=>flag,_=>error("Thread: solo hilo principal monohilo soportado")}}
fn thread_interrupt(h:&mut Heap,r:Option<usize>){let id=array_id(h,r);match &mut h.arrays[id]{Array::CurrentThread(flag,_)=>*flag=true,_=>error("Thread: solo hilo principal monohilo soportado")}}
fn thread_context_loader(h:&mut Heap,r:Option<usize>)->Option<usize>{let id=array_id(h,r);if !matches!(h.arrays[id],Array::CurrentThread(_,_)){error("Thread.getContextClassLoader: solo hilo principal monohilo soportado");}if let Some(value)=h.context_loader{return value;}if std::env::var_os("MC_AOT_STANDARD_CONTEXT_LOADER").as_deref()!=Some(std::ffi::OsStr::new("1")){error("Thread.getContextClassLoader: requiere MC_AOT_STANDARD_CONTEXT_LOADER=1");}let loader=Some(app_class_loader(h));h.context_loader=Some(loader);loader}
fn thread_set_context_loader(h:&mut Heap,r:Option<usize>,loader:Option<usize>){let id=array_id(h,r);if !matches!(h.arrays[id],Array::CurrentThread(_,_)){error("Thread.setContextClassLoader: solo hilo principal monohilo soportado");}if let Some(loader)=loader{if !matches!(h.arrays[loader],Array::AppLoader|Array::PlatformLoader){error("Thread.setContextClassLoader: cargador fuera del perfil");}}h.context_loader=Some(loader);}
fn thread_id(h:&Heap,r:Option<usize>)->i64{let id=array_id(h,r);if !matches!(h.arrays[id],Array::CurrentThread(_,_)){error("Thread.getId: solo hilo principal monohilo soportado");}let value=std::env::var("MC_AOT_JAVA_MAIN_THREAD_ID").unwrap_or_else(|_|error("Thread.getId: requiere MC_AOT_JAVA_MAIN_THREAD_ID positivo"));let id=value.parse::<i64>().unwrap_or_else(|_|error("Thread.getId: requiere MC_AOT_JAVA_MAIN_THREAD_ID positivo"));if id<=0{error("Thread.getId: requiere MC_AOT_JAVA_MAIN_THREAD_ID positivo");}id}
fn thread_name(h:&Heap,r:Option<usize>)->usize{let id=array_id(h,r);match h.arrays[id]{Array::CurrentThread(_,name)=>name,_=>error("Thread.getName: solo hilo principal monohilo soportado")}}
fn thread_set_name_guard(h:&Heap,r:Option<usize>,name:Option<usize>){let _=thread_name(h,r);if name.is_none(){raise("NullPointerException","name cannot be null");}error("Thread.setName: cambio de nombre no soportado")}
fn thread_interrupted(h:&mut Heap)->bool{let id=current_thread(h);if let Array::CurrentThread(flag,_)=&mut h.arrays[id]{let old=*flag;*flag=false;old}else{unreachable!()}}
fn collector_of(h:&mut Heap,supplier:Option<usize>,accumulator:Option<usize>,combiner:Option<usize>,characteristics:Option<usize>)->usize{let s=supplier.unwrap_or_else(||raise("NullPointerException",""));let a=accumulator.unwrap_or_else(||raise("NullPointerException",""));let c=combiner.unwrap_or_else(||raise("NullPointerException",""));let id=array_id(h,characteristics);if !matches!(&h.arrays[id],Array::ProjectRefs("java/util/stream/Collector$Characteristics",v) if v.is_empty()){error("Collector.of: solo características vacías");}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let out=h.arrays.len();h.arrays.push(Array::Collector(s,a,c));out}
// RuntimePermission es un objeto de datos; no implementa políticas ni checkPermission.
// Referentes solo null o el loader del sistema, que permanece fuertemente alcanzable.
fn weak_loader_new(h:&mut Heap)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::WeakLoader(None));id}
fn weak_loader_set(h:&mut Heap,r:Option<usize>,referent:Option<usize>){let id=array_id(h,r);if let Some(x)=referent{if !matches!(h.arrays[x],Array::AppLoader){error("WeakReference: solo ClassLoader de aplicación/null soportado");}}match &mut h.arrays[id]{Array::WeakLoader(value)=>*value=referent,_=>error("WeakReference: receptor fuera del perfil")}}
fn weak_loader_get(h:&Heap,r:Option<usize>)->Option<usize>{let id=array_id(h,r);match h.arrays[id]{Array::WeakLoader(value)=>value,_=>error("WeakReference: receptor fuera del perfil")}}
fn runtime_permission_new(h:&mut Heap)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::RuntimePermission(None));id}
fn runtime_permission_init(h:&mut Heap,r:Option<usize>,name:Option<usize>){let id=array_id(h,r);let name=array_id(h,name);if string_units(h,Some(name)).is_empty(){raise("IllegalArgumentException","name can't be empty");}match &mut h.arrays[id]{Array::RuntimePermission(slot)=>*slot=Some(name),_=>error("RuntimePermission: receptor fuera del perfil")}}
fn runtime_permission_name(h:&Heap,r:Option<usize>)->usize{let id=array_id(h,r);match h.arrays[id]{Array::RuntimePermission(Some(name))=>name,_=>error("RuntimePermission: receptor fuera del perfil")}}
fn runtime_singleton(h:&mut Heap)->usize{if let Some(id)=h.runtime_singleton{return id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::RuntimeSingleton);h.runtime_singleton=Some(id);id}
fn runtime_processors(h:&Heap,r:Option<usize>)->i32{let id=array_id(h,r);if !matches!(h.arrays[id],Array::RuntimeSingleton){error("Runtime concreto no soportado");}let n=std::env::var("MC_AOT_JAVA_PROCESSORS").unwrap_or_else(|_|error("Runtime.availableProcessors: configura MC_AOT_JAVA_PROCESSORS"));let value=n.parse::<i32>().unwrap_or_else(|_|error("MC_AOT_JAVA_PROCESSORS inválido"));if value<1{error("MC_AOT_JAVA_PROCESSORS debe ser positivo");}value}
fn system_line_separator(h:&mut Heap)->usize{if let Some(id)=h.line_separator{return id;}let units=if cfg!(windows){vec![13,10]}else{vec![10]};let id=new_string(h,units);h.line_separator=Some(id);id}
fn process_current(h:&mut Heap)->usize{if let Some(id)=h.current_process{return id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::CurrentProcess);h.current_process=Some(id);id}
fn process_pid(h:&Heap,r:Option<usize>)->i64{let id=array_id(h,r);if !matches!(h.arrays[id],Array::CurrentProcess){error("ProcessHandle concreto no soportado");}std::process::id() as i64}
fn long_to_string(h:&mut Heap,n:i64)->usize{new_string(h,n.to_string().encode_utf16().collect())}
fn clock_millis()->i64{let millis=match std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH){Ok(d)=>i128::try_from(d.as_millis()).unwrap_or(i128::MAX),Err(e)=>-i128::try_from(e.duration().as_millis().saturating_add(if e.duration().subsec_nanos()%1_000_000!=0{1}else{0})).unwrap_or(i128::MAX)};i64::try_from(millis).unwrap_or_else(|_|error("reloj fuera de rango Java"))}
// Perfil explícito: ISO con año de cuatro dígitos, segundos y offset numérico o Z, sin zona nombrada.
fn zoned_parse(h:&mut Heap,r:Option<usize>)->usize{let units=string_units(h,r);let s=String::from_utf16(units).unwrap_or_else(|_|error("ZonedDateTime.parse: texto inválido no soportado"));let b=s.as_bytes();if b.len()<20||b.get(4)!=Some(&b'-')||b.get(7)!=Some(&b'-')||b.get(10)!=Some(&b'T')||b.get(13)!=Some(&b':')||b.get(16)!=Some(&b':'){error("ZonedDateTime.parse: formato fuera del perfil");}fn num(b:&[u8],a:usize,n:usize)->i64{let mut v=0;for &x in b.get(a..a+n).unwrap_or_else(||error("ZonedDateTime.parse: formato fuera del perfil")){if !x.is_ascii_digit(){error("ZonedDateTime.parse: formato fuera del perfil");}v=v*10+(x-b'0') as i64;}v}
 let y=num(b,0,4);let m=num(b,5,2);let d=num(b,8,2);let hh=num(b,11,2);let mm=num(b,14,2);let ss=num(b,17,2);let mut p=19;let mut nanos=0i32;if b.get(p)==Some(&b'.'){p+=1;let start=p;while p<b.len()&&b[p].is_ascii_digit(){if p-start>=9{error("ZonedDateTime.parse: fracción fuera del perfil");}nanos=nanos*10+(b[p]-b'0') as i32;p+=1;}if p==start{error("ZonedDateTime.parse: fracción vacía");}for _ in p-start..9{nanos*=10;}}
 let offset=if b.get(p)==Some(&b'Z')&&p+1==b.len(){0}else{if p+6!=b.len()||!matches!(b[p],b'+'|b'-')||b[p+3]!=b':'{error("ZonedDateTime.parse: offset fuera del perfil");}let oh=num(b,p+1,2);let om=num(b,p+4,2);if oh>18||om>59||(oh==18&&om!=0){error("ZonedDateTime.parse: offset inválido");}let sign=if b[p]==b'-'{-1}else{1};sign*(oh*3600+om*60)};
 let leap=y%4==0&&(y%100!=0||y%400==0);let max=match m{1|3|5|7|8|10|12=>31,4|6|9|11=>30,2=>if leap{29}else{28},_=>error("ZonedDateTime.parse: mes inválido")};if d<1||d>max||hh>23||mm>59||ss>59{error("ZonedDateTime.parse: fecha inválida");}let yr=y-if m<=2{1}else{0};let era=yr.div_euclid(400);let yoe=yr-era*400;let mp=m+if m>2{-3}else{9};let doy=(153*mp+2)/5+d-1;let days=era*146097+yoe*365+yoe/4-yoe/100+doy-719468;let epoch=days*86400+hh*3600+mm*60+ss-offset;if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Zoned(epoch,nanos));id}
fn zoned_to_instant(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);let (s,n)=match h.arrays[id]{Array::Zoned(s,n)=>(s,n),_=>error("ZonedDateTime concreto no soportado")};if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Instant(s,n));id}
fn instant_millis(h:&Heap,r:Option<usize>)->i64{let id=array_id(h,r);let (s,n)=match h.arrays[id]{Array::Instant(s,n)=>(s,n),_=>error("Instant concreto no soportado")};i64::try_from((s as i128)*1000+(n/1_000_000) as i128).unwrap_or_else(|_|raise("ArithmeticException",""))}
fn date_to_instant(h:&mut Heap,r:Option<usize>)->usize{let value=date_get(h,r);let secs=value.div_euclid(1000);let nanos=(value.rem_euclid(1000)*1_000_000) as i32;if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Instant(secs,nanos));id}
fn date_from_instant(h:&mut Heap,r:Option<usize>)->usize{let v=instant_millis(h,r);let id=date_new(h);date_set(h,Some(id),v);id}
fn date_new(h:&mut Heap)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Date(0));id}
fn date_get(h:&Heap,r:Option<usize>)->i64{let id=array_id(h,r);match h.arrays[id]{Array::Date(n)=>n,_=>error("Date concreto no soportado")}}
fn date_set(h:&mut Heap,r:Option<usize>,value:i64){let id=array_id(h,r);match &mut h.arrays[id]{Array::Date(n)=>*n=value,_=>error("Date concreto no soportado")}}
fn uuid_random(h:&mut Heap)->usize{use std::io::Read;let mut bytes=[0u8;16];let mut f=std::fs::File::open("/dev/urandom").unwrap_or_else(|_|error("UUID.randomUUID: fuente de entropía no disponible"));f.read_exact(&mut bytes).unwrap_or_else(|_|error("UUID.randomUUID: fallo de entropía"));bytes[6]=(bytes[6]&0x0f)|0x40;bytes[8]=(bytes[8]&0x3f)|0x80;if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Uuid(bytes));id}
fn uuid_bytes(h:&Heap,r:Option<usize>)->[u8;16]{let id=array_id(h,r);match h.arrays[id]{Array::Uuid(bytes)=>bytes,_=>error("UUID concreto no soportado")}}
fn uuid_parts(h:&Heap,r:Option<usize>)->(u8,u8){let b=uuid_bytes(h,r);(b[6]>>4,if b[8]&0x80==0{0}else if b[8]&0xc0==0x80{2}else if b[8]&0xe0==0xc0{6}else{7})}
fn uuid_string(h:&mut Heap,r:Option<usize>)->usize{let b=uuid_bytes(h,r);let mut text=String::with_capacity(36);for (i,x) in b.iter().enumerate(){if matches!(i,4|6|8|10){text.push('-');}text.push_str(&format!("{x:02x}"));}new_string(h,text.encode_utf16().collect())}
fn string_matches_formatting(h:&Heap,r:Option<usize>,pattern:Option<usize>)->bool{let text=string_units(h,r);let p=string_units(h,pattern);let newline:Vec<u16>=r"[\r\n]*".encode_utf16().collect();let indent:Vec<u16>=r"[ \t]*".encode_utf16().collect();if p==newline{text.iter().all(|c|*c==10||*c==13)}else if p==indent{text.iter().all(|c|*c==32||*c==9)}else{error("String.matches: regex fuera del perfil verificado")}}
fn string_replace_dash(h:&mut Heap,r:Option<usize>,pattern:Option<usize>,repl:Option<usize>)->usize{let id=array_id(h,r);if string_units(h,pattern)!=[45u16]||!string_units(h,repl).is_empty(){error("String.replaceAll: patrón/reemplazo fuera del perfil verificado");}let units=string_units(h,r);if !units.contains(&45){return id;}let out=units.iter().copied().filter(|c|*c!=45).collect();new_string(h,out)}
fn pattern_compile(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);let pattern=string_units(h,r);let expected:Vec<u16>=r"%(?:(\d+)\$)?([A-Za-z%]|$)".encode_utf16().collect();if pattern!=expected && !pattern.iter().copied().eq(r"([A-Z]*[a-z0-9]+|[A-Z0-9]+)[-._/]?".encode_utf16()){error("Pattern.compile: expresión regular fuera del perfil verificado");}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let result=h.arrays.len();h.arrays.push(Array::Pattern(id,0));result}
fn pattern_compile_duration(h:&mut Heap,r:Option<usize>,flags:i32)->usize{if flags!=2{error("Pattern.compile: flags fuera del perfil verificado");}let id=array_id(h,r);let pat=string_units(h,r);if !pat.iter().copied().eq(r"([+-]?\d+)\s*(\w+)?".encode_utf16())&&!pat.iter().copied().eq(r"(^log4j2?[-._/]?|^org\.apache\.logging\.log4j\.)|(?=AsyncLogger(Config)?\.)".encode_utf16()){error("Pattern.compile: expresión regular fuera del perfil verificado");}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let result=h.arrays.len();h.arrays.push(Array::Pattern(id,flags));result}
fn property_pattern_kind(h:&Heap,id:usize)->u8{let (s,flags)=match h.arrays[id]{Array::Pattern(s,f)=>(s,f),_=>error("Pattern concreto no soportado")};let pat=string_units(h,Some(s));if flags==2&&pat.iter().copied().eq(r"(^log4j2?[-._/]?|^org\.apache\.logging\.log4j\.)|(?=AsyncLogger(Config)?\.)".encode_utf16()){1}else if flags==0&&pat.iter().copied().eq(r"([A-Z]*[a-z0-9]+|[A-Z0-9]+)[-._/]?".encode_utf16()){2}else{0}}
fn regex_input(h:&Heap,id:usize)->&[u16]{match &h.arrays[id]{Array::Str(v)|Array::Builder(v)=>v,_=>error("Matcher: CharSequence fuera del perfil")}}
fn pattern_matcher(h:&mut Heap,r:Option<usize>,input:Option<usize>)->usize{let p=array_id(h,r);let i=array_id(h,input);if property_pattern_kind(h,p)==0{error("Pattern.matcher: expresión fuera del perfil de propiedades");}let _=regex_input(h,i);if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let out=h.arrays.len();h.arrays.push(Array::Matcher(p,i,None));out}
fn matcher_find(h:&mut Heap,r:Option<usize>,start:i32)->bool{let id=array_id(h,r);let (p,i)=match h.arrays[id]{Array::Matcher(p,i,_)=>(p,i),_=>error("Matcher concreto no soportado")};let kind=property_pattern_kind(h,p);let text=regex_input(h,i);if start<0||start as usize>text.len(){raise("IndexOutOfBoundsException","Illegal start index");}let start=start as usize;
 let lower=|v:u16|if (65..=90).contains(&v){v+32}else{v};let ci=|pos:usize,s:&str|text.get(pos..pos+s.len()).is_some_and(|slice|slice.iter().copied().map(lower).eq(s.bytes().map(|b|b as u16)));let delim=|x:u16|matches!(x,45|46|95|47);let upper=|x:u16|(65..=90).contains(&x);let lowdigit=|x:u16|(97..=122).contains(&x)||(48..=57).contains(&x);let updigit=|x:u16|upper(x)||(48..=57).contains(&x);
 let mut found=None;if kind==1 {if start==0&&ci(0,"log4j"){let mut end=5;if text.get(end)==Some(&50){end+=1;}if text.get(end).is_some_and(|x|delim(*x)){end+=1;}found=Some((0,end,Some((0,end))));}else if start==0&&ci(0,"org.apache.logging.log4j."){let end="org.apache.logging.log4j.".len();found=Some((0,end,Some((0,end))));}else{for pos in start..=text.len(){if ci(pos,"asynclogger"){let end=pos+11;let ok=if ci(end,"config"){text.get(end+6)==Some(&46)}else{text.get(end)==Some(&46)};if ok{found=Some((pos,pos,None));break;}}}}}else if kind==2{for pos in start..text.len(){let mut j=pos;while j<text.len()&&upper(text[j]){j+=1;}let mut k=j;while k<text.len()&&lowdigit(text[k]){k+=1;}if k==j{k=pos;while k<text.len()&&updigit(text[k]){k+=1;}}if k>pos{let end=if text.get(k).is_some_and(|x|delim(*x)){k+1}else{k};found=Some((pos,end,Some((pos,k))));break;}}}else{error("Matcher.find: patrón fuera del perfil");}if let Array::Matcher(_,_,slot)=&mut h.arrays[id]{*slot=found;}found.is_some()}
fn matcher_end(h:&Heap,r:Option<usize>)->i32{let id=array_id(h,r);match h.arrays[id]{Array::Matcher(_,_,Some((_,end,_)))=>end as i32,Array::Matcher(_,_,None)=>raise("IllegalStateException","No match found"),_=>error("Matcher concreto no soportado")}}
fn matcher_group(h:&mut Heap,r:Option<usize>,group:i32)->Option<usize>{let id=array_id(h,r);let (p,input,result)=match h.arrays[id]{Array::Matcher(p,i,m)=>(p,i,m),_=>error("Matcher concreto no soportado")};let (_,_,g)=result.unwrap_or_else(||raise("IllegalStateException","No match found"));if group!=1||property_pattern_kind(h,p)!=2{error("Matcher.group: solo grupo 1 del tokenizer soportado");}let (a,b)=g.unwrap_or_else(||error("Matcher.group: grupo ausente"));let text=regex_input(h,input);if b>text.len(){error("Matcher.group: entrada modificada fuera del perfil");}let units=text[a..b].to_vec();Some(new_string(h,units))}
fn pattern_flags(h:&Heap,r:Option<usize>)->i32{let id=array_id(h,r);match h.arrays[id]{Array::Pattern(_,flags)=>flags,_=>error("Pattern concreto no soportado")}}
fn pattern_string(h:&Heap,r:Option<usize>)->Option<usize>{let id=array_id(h,r);match h.arrays[id]{Array::Pattern(s,_)=>Some(s),_=>error("Pattern concreto no soportado")}}
fn optional_new(h:&mut Heap,value:Option<usize>)->usize{if value.is_none(){if let Some(id)=h.optional_empty{return id;}}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Optional(value));if value.is_none(){h.optional_empty=Some(id);}id}
fn optional_value(h:&Heap,r:Option<usize>)->Option<usize>{let id=array_id(h,r);match h.arrays[id]{Array::Optional(value)=>value,_=>error("Optional concreto no soportado")}}
fn identity_function(h:&mut Heap)->usize{if let Some(id)=h.identity_function{return id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::IdentityFunction);h.identity_function=Some(id);id}
fn locale_root(h:&mut Heap)->usize{if let Some(id)=h.root_locale{return id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::RootLocale);h.root_locale=Some(id);id}
fn crash_date_formatter(h:&mut Heap,pattern:Option<usize>,locale:Option<usize>)->usize{let p=string_units(h,pattern);let expected:Vec<u16>="yyyy-MM-dd HH:mm:ss".encode_utf16().collect();if p!=expected{error("DateTimeFormatter.ofPattern: patrón fuera del perfil");}let id=array_id(h,locale);if !matches!(h.arrays[id],Array::RootLocale){error("DateTimeFormatter.ofPattern: locale fuera del perfil");}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::CrashDateFormatter);id}
fn iso_instant_formatter(h:&mut Heap)->usize{if let Some(id)=h.iso_instant{return id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::IsoInstantFormatter);h.iso_instant=Some(id);id}
fn lambda_new(h:&mut Heap,site:usize,interface:&'static str,captures:Vec<V>)->usize{if captures.is_empty(){if let Some(id)=h.lambdas.get(&site){return *id;}}if h.arrays.len()>=10000||h.elements.saturating_add(captures.len())>1_000_000{error("Límite experimental de heap excedido");}h.elements+=captures.len();let empty=captures.is_empty();let id=h.arrays.len();h.arrays.push(Array::Lambda(site,interface,captures));if empty{h.lambdas.insert(site,id);}id}
fn project_instance(h:&Heap,r:Option<usize>,target:&str,interfaces:&[(&str,&str)])->bool {
    match r.and_then(|id|h.arrays.get(id)) {
        Some(Array::Obj(actual,_)|Array::SharedObj(actual,_)|Array::LocalObj(actual,_,_))=>project_subtype(h,actual,target)||interfaces.iter().any(|(c,i)|*c==*actual && *i==target),
        Some(Array::IdentityFunction)=>target=="java/util/function/Function",
        Some(Array::Lambda(_,interface,_))=>*interface==target||interfaces.iter().any(|(c,i)|*c==*interface&&*i==target),
        Some(Array::Exception(kind,_,_)) if kind.contains('/')=>error("cast de excepción Minecraft a tipo proyecto no soportado"),
        _=>false,
    }
}

// Panic solo transporta excepciones JVM representadas; errores internos siguen siendo panics Rust.
#[derive(Debug)] struct JException {kind:&'static str, message:&'static str, id:Option<usize>}
fn raise(kind:&'static str,message:&'static str)->! {std::panic::panic_any(JException{kind,message,id:None})}
fn throw_ref(h:&Heap,r:Option<usize>)->! {
    let id=array_id(h,r);
    match h.arrays[id] {Array::Exception(kind,message,_)=>std::panic::panic_any(JException{kind,message,id:Some(id)}),_=>panic!("athrow requiere Throwable admitido")}
}
fn exception_ref(h:&mut Heap,e:&JException)->usize {
    if let Some(id)=e.id {return id;}
    if h.arrays.len()>=10000 {error("Límite experimental de heap excedido");}
    let id=h.arrays.len();h.arrays.push(Array::Exception(e.kind,e.message,None));let msg=if e.message.is_empty(){None}else{Some(new_string(h,e.message.encode_utf16().collect()))};h.exception_messages.insert(id,msg);id
}
fn exception_instance(h:&Heap,r:Option<usize>,target:&str)->bool{match r.and_then(|id|h.arrays.get(id)){Some(Array::Exception(kind,_,_))=>exception_matches(kind,target),_=>false}}
fn exception_matches(kind:&str,catch:&str)->bool {
    if catch.is_empty() || catch=="java/lang/Throwable" {return true;}
    if kind.contains('/') && !kind.starts_with("java/") {
        let mut t=kind;
        while t.contains('/') && !t.starts_with("java/") {if t==catch{return true;}t=match user_exception_parent(t){Some(p)=>p,None=>panic!("jerarquía de excepción no registrada")};}
        return exception_matches(t.rsplit('/').next().unwrap_or(t),catch);
    }
    let mut t=kind;
    loop {
        let full=match t {"URISyntaxException"=>"java/net/URISyntaxException".to_owned(),"IOException"=>"java/io/IOException".to_owned(),"FileNotFoundException"=>"java/io/FileNotFoundException".to_owned(),"FileSystemException"|"NoSuchFileException"|"AccessDeniedException"=>format!("java/nio/file/{t}"),"UncheckedIOException"=>"java/io/UncheckedIOException".to_owned(),"DateTimeException"=>"java/time/DateTimeException".to_owned(),"InvocationTargetException"=>"java/lang/reflect/InvocationTargetException".to_owned(),"ServiceConfigurationError"=>"java/util/ServiceConfigurationError".to_owned(),"NoSuchElementException"=>"java/util/NoSuchElementException".to_owned(),"ConcurrentModificationException"=>"java/util/ConcurrentModificationException".to_owned(),_=>format!("java/lang/{t}")};
        if full==catch {return true;}
        t=match t {
            "Throwable"=>return false,
            "Exception"|"Error"=>"Throwable",
            "LinkageError"|"VirtualMachineError"|"ServiceConfigurationError"|"AssertionError"=>"Error",
            "InternalError"=>"VirtualMachineError",
            "ExceptionInInitializerError"|"NoClassDefFoundError"=>"LinkageError",
            "NoSuchFileException"|"AccessDeniedException"=>"FileSystemException",
            "FileSystemException"|"FileNotFoundException"=>"IOException",
            "IOException"|"URISyntaxException"|"RuntimeException"|"ReflectiveOperationException"|"InterruptedException"=>"Exception",
            "ClassNotFoundException"|"NoSuchMethodException"|"InstantiationException"|"IllegalAccessException"|"InvocationTargetException"=>"ReflectiveOperationException",
            "NumberFormatException"=>"IllegalArgumentException",
            "ArrayIndexOutOfBoundsException"|"StringIndexOutOfBoundsException"=>"IndexOutOfBoundsException",
            "UncheckedIOException"|"DateTimeException"|"IllegalArgumentException"|"IllegalStateException"|"IllegalCallerException"|"IndexOutOfBoundsException"|"ArithmeticException"|"NullPointerException"|"NegativeArraySizeException"|"ClassCastException"|"ArrayStoreException"|"SecurityException"|"IllegalMonitorStateException"|"UnsupportedOperationException"|"NoSuchElementException"|"ConcurrentModificationException"=>"RuntimeException",
            _=>return false,
        };
    }
}
fn run_java(f:impl FnOnce()) {
    let old=std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {if !info.payload().is::<JException>() {old(info)}}));
    if let Err(payload)=std::panic::catch_unwind(std::panic::AssertUnwindSafe(f)) {
        if let Some(e)=payload.downcast_ref::<JException>() {if e.message.is_empty(){eprintln!("{}",e.kind)}else{eprintln!("{}: {}",e.kind,e.message)}std::process::exit(2);}
        std::panic::resume_unwind(payload);
    }
}

fn new_exception(h:&mut Heap,kind:&'static str)->usize {
    if h.arrays.len()>=10000 {error("Límite experimental de heap excedido");}
    let id=h.arrays.len();h.arrays.push(Array::Exception(kind,"",None));id
}
fn init_exception(h:&mut Heap,r:Option<usize>,kind:&str,message:Option<usize>) {
    let id=array_id(h,r);if let Some(m)=message {let _=string_units(h,Some(m));}
    match &mut h.arrays[id] {Array::Exception(k,_,m) if *k==kind=>*m=message,_=>panic!("constructor de excepción con tipo incompatible")};h.exception_messages.insert(id,message);
}
fn require_non_null(h:&mut Heap,value:Option<usize>,message:Option<usize>)->Option<usize>{if value.is_some(){return value;}let id=new_exception(h,"NullPointerException");init_exception(h,Some(id),"NullPointerException",message);throw_ref(h,Some(id))}
fn init_exception_cause(h:&mut Heap,r:Option<usize>,kind:&str,message:Option<usize>,cause:Option<usize>){
    init_exception(h,r,kind,message);let id=array_id(h,r);if let Some(c)=cause {if !matches!(h.arrays.get(c),Some(Array::Exception(_,_,_))){error("Throwable causa no soportada");}h.causes.insert(id,c);}
}
fn init_exception_from_io_cause(h:&mut Heap,r:Option<usize>,kind:&str,cause:Option<usize>){if cause.is_none(){raise("NullPointerException","");}init_exception_from_cause(h,r,kind,cause)}
fn init_exception_from_cause(h:&mut Heap,r:Option<usize>,kind:&str,cause:Option<usize>){let message=if let Some(id)=cause{let (kind,static_msg)=match h.arrays.get(id){Some(Array::Exception(k,m,_))=>(*k,*m),_=>error("Throwable causa no soportada")};if kind.contains('/') || kind=="URISyntaxException" {error("Throwable(cause): toString de excepción fuera del perfil");}let full=match kind{"IOException"=>"java.io.IOException".to_owned(),"FileNotFoundException"=>"java.io.FileNotFoundException".to_owned(),"FileSystemException"|"NoSuchFileException"|"AccessDeniedException"=>format!("java.nio.file.{kind}"),"UncheckedIOException"=>"java.io.UncheckedIOException".to_owned(),"NoSuchElementException"=>"java.util.NoSuchElementException".to_owned(),"ConcurrentModificationException"=>"java.util.ConcurrentModificationException".to_owned(),"ServiceConfigurationError"=>"java.util.ServiceConfigurationError".to_owned(),"InvocationTargetException"=>"java.lang.reflect.InvocationTargetException".to_owned(),_=>format!("java.lang.{kind}")};let mut units:Vec<u16>=full.encode_utf16().collect();let dynamic=h.exception_messages.get(&id).copied().flatten();if let Some(msg)=dynamic{units.extend(": ".encode_utf16());units.extend_from_slice(string_units(h,Some(msg)));}else if !static_msg.is_empty(){units.extend(": ".encode_utf16());units.extend(static_msg.encode_utf16());}Some(new_string(h,units))}else{None};init_exception_cause(h,r,kind,message,cause)}
fn exception_add_suppressed(h:&mut Heap,r:Option<usize>,other:Option<usize>){let id=array_id(h,r);if !matches!(h.arrays[id],Array::Exception(_,_,_)){error("Throwable.addSuppressed: receptor no soportado");}let other=other.unwrap_or_else(||raise("NullPointerException",""));if id==other{raise("IllegalArgumentException","");}if !matches!(h.arrays.get(other),Some(Array::Exception(_,_,_))){error("Throwable.addSuppressed: argumento no soportado");}if h.elements>=1_000_000{error("Límite experimental de heap excedido");}h.elements+=1;h.suppressed.entry(id).or_default().push(other);}
fn uri_syntax_init(h:&mut Heap,r:Option<usize>,input:Option<usize>,reason:Option<usize>,index:i32){let id=array_id(h,r);let input=array_id(h,input);let reason=array_id(h,reason);string_units(h,Some(input));string_units(h,Some(reason));if index< -1{raise("IllegalArgumentException","");}init_exception(h,r,"URISyntaxException",Some(reason));h.uri_syntax.insert(id,(input,reason,index));}
fn uri_syntax_part(h:&Heap,r:Option<usize>,input:bool)->usize{let id=array_id(h,r);let (a,b,_)=h.uri_syntax.get(&id).copied().unwrap_or_else(||error("URISyntaxException no inicializada"));if input{a}else{b}}
fn uri_syntax_index(h:&Heap,r:Option<usize>)->i32{let id=array_id(h,r);h.uri_syntax.get(&id).unwrap_or_else(||error("URISyntaxException no inicializada")).2}
fn exception_message(h:&mut Heap,r:Option<usize>)->Option<usize>{let id=array_id(h,r);if let Some((input,reason,index))=h.uri_syntax.get(&id).copied(){let mut units=string_units(h,Some(reason)).to_vec();if index> -1{units.extend(format!(" at index {index}").encode_utf16());}units.extend(": ".encode_utf16());units.extend_from_slice(string_units(h,Some(input)));return Some(new_string(h,units));}match h.exception_messages.get(&id){Some(v)=>*v,None=>error("Throwable.getMessage: excepción no construida por el runtime admitido")}}


// Formato diagnóstico estable de arrays; String[] conserva exactamente unidades UTF-16.
fn array_render(h:&Heap,r:Option<usize>)->String {
    let id=match r {None=>return "null".into(),Some(id)=>id};
    let text=match h.arrays.get(id).expect("referencia inválida") {
        Array::Z(v)=>v.iter().map(|x|if *x {"1".to_owned()}else{"0".to_owned()}).collect::<Vec<_>>().join(","),
        Array::B(v)=>v.iter().map(|x|x.to_string()).collect::<Vec<_>>().join(","),
        Array::C(v)=>v.iter().map(|x|x.to_string()).collect::<Vec<_>>().join(","),
        Array::S(v)=>v.iter().map(|x|x.to_string()).collect::<Vec<_>>().join(","),
        Array::I(v)=>v.iter().map(|x|x.to_string()).collect::<Vec<_>>().join(","),
        Array::J(v)=>v.iter().map(|x|x.to_string()).collect::<Vec<_>>().join(","),
        Array::Strings(v)=> {
            let entries=v.iter().map(|r|match r {None=>"n".to_owned(),Some(_)=>format!("x{}",string_units(h,*r).iter().map(|c|format!("{c:04x}")).collect::<String>())}).collect::<Vec<_>>().join(",");
            return format!("sarr16:[{entries}]");
        },
        _=>panic!("se esperaba array"),
    };
    format!("[{text}]")
}

// Objetos concretos de clase directa de Object; sin subtipos ni despacho de interfaces.
fn timeunit_get(h:&mut Heap,unit:u8)->usize{let i=unit as usize;if i>=7{error("TimeUnit inválido");}if let Some(id)=h.time_units[i]{return id;}let names=["NANOSECONDS","MICROSECONDS","MILLISECONDS","SECONDS","MINUTES","HOURS","DAYS"];let name=string_literal(h,&names[i].encode_utf16().collect::<Vec<_>>());if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::TimeUnit(unit));h.time_units[i]=Some(id);h.enum_values.insert(id,(Some(name),unit as i32));id}
fn timeunit_id(h:&Heap,r:Option<usize>)->u8{let id=array_id(h,r);match h.arrays[id]{Array::TimeUnit(n)=>n,_=>error("TimeUnit: receptor fuera del perfil")}}
fn timeunit_convert(h:&Heap,dest:Option<usize>,value:i64,source:Option<usize>)->i64{let dst=timeunit_id(h,dest);let src=timeunit_id(h,source);timeunit_convert_indices(dst,src,value)}
fn timeunit_convert_indices(dst:u8,src:u8,value:i64)->i64{const NANOS:[i128;7]=[1,1000,1_000_000,1_000_000_000,60_000_000_000,3_600_000_000_000,86_400_000_000_000];let result=(value as i128)*NANOS[src as usize]/NANOS[dst as usize];result.clamp(i64::MIN as i128,i64::MAX as i128) as i64}
fn timeunit_to(h:&Heap,r:Option<usize>,value:i64,dst:u8)->i64{let src=timeunit_id(h,r);timeunit_convert_indices(dst,src,value)}
fn enum_init(h:&mut Heap,r:Option<usize>,name:Option<usize>,ordinal:i32){
    let id=array_id(h,r);if !matches!(h.arrays[id],Array::Obj(_, _)|Array::SharedObj(_, _)){panic!("se esperaba enum");}
    if h.enum_values.insert(id,(name,ordinal)).is_some(){panic!("enum inicializado dos veces");}
}
// Enum.valueOf para values() canónico verificado en compilación. Los nombres
// y valores se guardan al primer acceso, como el directorio de Class de Java.
fn enum_valueof_array(h:&mut Heap,class:&'static str,name:Option<usize>,slot:usize,canonical:Option<&'static str>)->Option<usize>{
    if !h.enum_directories.contains_key(class){
        let array=match h.fields.get(slot){Some(V::R(Some(id)))=>*id,_=>error("Enum.valueOf: values aún no disponible")};
        let vals=match h.arrays.get(array){Some(Array::ProjectRefs(c,v)) if *c==class=>v.clone(),_=>error("Enum.valueOf: array fuera del perfil")};
        if h.elements.checked_add(vals.len()).map_or(true,|n|n>1_000_000){error("Enum.valueOf: límite experimental de heap excedido");}
        h.elements+=vals.len();let mut entries=Vec::with_capacity(vals.len());
        for value in vals {let id=value.unwrap_or_else(||error("Enum.valueOf: valor nulo fuera del perfil"));let n=h.enum_values.get(&id).and_then(|(n,_)|*n).unwrap_or_else(||error("Enum.valueOf: valor no inicializado"));entries.push((n,id));}
        h.enum_directories.insert(class,entries);
    }
    if name.is_none(){raise("NullPointerException","Name is null");}
    let text=string_units(h,name);
    let found=h.enum_directories[class].iter().rev().find(|(n,_)|string_units(h,Some(*n))==text).map(|(_,v)|*v);
    if let Some(value)=found{return Some(value);}
    let canonical=canonical.unwrap_or_else(||error("Enum.valueOf: nombre canónico anidado no modelado"));
    let mut msg:Vec<u16>="No enum constant ".encode_utf16().collect();msg.extend(canonical.encode_utf16());msg.push('.' as u16);msg.extend_from_slice(text);
    let m=new_string(h,msg);let e=new_exception(h,"IllegalArgumentException");init_exception(h,Some(e),"IllegalArgumentException",Some(m));throw_ref(h,Some(e))
}
fn enum_ordinal(h:&Heap,r:Option<usize>)->i32{let id=array_id(h,r);h.enum_values.get(&id).expect("enum no inicializado").1}
fn enum_name(h:&Heap,r:Option<usize>)->Option<usize>{let id=array_id(h,r);h.enum_values.get(&id).expect("enum no inicializado").0}
fn object_new(h:&mut Heap,class:&'static str,fields:Vec<V>,local:bool)->usize {
    if h.arrays.len()>=10000 || h.elements.checked_add(fields.len()).map_or(true,|v|v>1_000_000){error("Límite experimental de heap excedido");}
    let id=h.arrays.len();h.elements+=fields.len();h.arrays.push(if local {Array::LocalObj(class,fields,None)}else{Array::Obj(class,fields)});id
}
fn object_id(h:&Heap,r:Option<usize>,class:&str)->usize {
    let id=array_id(h,r);match &h.arrays[id] {Array::Obj(actual,_)|Array::SharedObj(actual,_)|Array::LocalObj(actual,_,_) if project_subtype(h,actual,class)=>id,_=>panic!("despacho de objeto no soportado")}
}
fn check_object_class(h:&Heap,r:Option<usize>,class:&str){let _=object_id(h,r,class);}
fn check_any_object(h:&Heap,r:Option<usize>){let id=array_id(h,r);if !matches!(h.arrays[id],Array::Obj(_, _)|Array::SharedObj(_,_)|Array::LocalObj(_,_,_)){panic!("constructor Object sobre referencia no admitida")}}
fn object_load(h:&Heap,r:Option<usize>,class:&str,slot:usize)->V {
    let id=object_id(h,r,class);match &h.arrays[id] {Array::Obj(_,f)|Array::LocalObj(_,f,_)=>f[slot],Array::SharedObj(_,f)=>f.fields.lock().expect("objeto compartido dañado")[slot],_=>unreachable!()}
}
fn object_store(h:&mut Heap,r:Option<usize>,class:&str,slot:usize,value:V){
    let id=object_id(h,r,class);match &mut h.arrays[id] {Array::Obj(_,f)|Array::LocalObj(_,f,_)=>f[slot]=value,Array::SharedObj(_,f)=>f.fields.lock().expect("objeto compartido dañado")[slot]=value,_=>unreachable!()}
}

// Puente experimental para campos de objetos del backend numérico. No permite
// ejecutar bytecode en hilos ni obtener índices de referencia o el Mutex externo.
// Las operaciones nunca retienen el lock al devolver ni ejecutan callbacks.
#[derive(Default)] struct SharedMonitorState { owner:Option<std::thread::ThreadId>,depth:usize }
#[derive(Default)] struct SharedMonitor {state:std::sync::Mutex<SharedMonitorState>,changed:std::sync::Condvar}
impl SharedMonitor {
    fn enter(&self)->Result<(),&'static str>{
        let current=std::thread::current().id();let mut s=self.state.lock().map_err(|_|"monitor dañado")?;
        while s.owner.is_some()&&s.owner!=Some(current){s=self.changed.wait(s).map_err(|_|"monitor dañado")?;}
        s.depth=s.depth.checked_add(1).ok_or("límite de monitor excedido")?;s.owner=Some(current);Ok(())
    }
    fn exit(&self)->Result<(),&'static str>{
        let current=std::thread::current().id();let mut s=self.state.lock().map_err(|_|"monitor dañado")?;
        if s.owner!=Some(current)||s.depth==0{return Err("monitor no adquirido");}
        s.depth-=1;if s.depth==0{s.owner=None;self.changed.notify_one();}Ok(())
    }
    fn holds(&self)->Result<bool,&'static str>{let s=self.state.lock().map_err(|_|"monitor dañado")?;Ok(s.owner==Some(std::thread::current().id())&&s.depth>0)}
}
struct NumericMonitorGuard {monitor:std::sync::Arc<SharedMonitor>,not_send:std::marker::PhantomData<std::rc::Rc<()>>}
impl Drop for NumericMonitorGuard {fn drop(&mut self){self.monitor.exit().expect("salida de monitor inválida");}}
#[derive(Clone)] struct NumericObjectHandle { fields:std::sync::Arc<std::sync::Mutex<Vec<V>>>, monitor:std::sync::Arc<SharedMonitor> }
impl NumericObjectHandle {
    fn read_int(&self,slot:usize)->Result<i32,&'static str>{
        let fields=self.fields.lock().map_err(|_|"objeto compartido dañado")?;
        match fields.get(slot){Some(V::I(n))=>Ok(*n),Some(_)=>Err("campo no int"),None=>Err("campo inexistente")}
    }
    // Operación explícitamente atómica del experimento, NO equivale a i++ Java.
    fn add_int(&self,slot:usize,delta:i32)->Result<i32,&'static str>{
        let mut fields=self.fields.lock().map_err(|_|"objeto compartido dañado")?;
        match fields.get_mut(slot){Some(V::I(n))=>{let old=*n;*n=n.wrapping_add(delta);Ok(old)},Some(_)=>Err("campo no int"),None=>Err("campo inexistente")}
    }
    fn write_int(&self,slot:usize,value:i32)->Result<(),&'static str>{let mut f=self.fields.lock().map_err(|_|"objeto compartido dañado")?;match f.get_mut(slot){Some(V::I(n))=>{*n=value;Ok(())},Some(_)=>Err("campo no int"),None=>Err("campo inexistente")}}
    fn enter_monitor(&self)->Result<NumericMonitorGuard,&'static str>{self.monitor.enter()?;Ok(NumericMonitorGuard{monitor:self.monitor.clone(),not_send:std::marker::PhantomData})}
    fn same_object(&self,other:&Self)->bool{std::sync::Arc::ptr_eq(&self.fields,&other.fields)}
}
fn share_project_object(h:&mut Heap,id:usize)->Result<NumericObjectHandle,&'static str>{
    if h.monitors.get(&id).copied().unwrap_or(0)>0{return Err("monitor monohilo adquirido");}
    let item=h.arrays.get_mut(id).ok_or("referencia inválida")?;
    match item {
        Array::SharedObj(_,handle)=>Ok(handle.clone()),
        Array::Obj(class,fields)=>{let class=*class;let handle=NumericObjectHandle{fields:std::sync::Arc::new(std::sync::Mutex::new(std::mem::take(fields))),monitor:std::sync::Arc::new(SharedMonitor::default())};*item=Array::SharedObj(class,handle.clone());Ok(handle)},
        _=>Err("solo objetos de proyecto ordinarios"),
    }
}
// Las referencias crudas son índices locales al heap; no se transfieren a otro.
fn resolve_shared_object(h:&Heap,handle:&NumericObjectHandle)->Result<usize,&'static str>{
    h.arrays.iter().position(|a|matches!(a,Array::SharedObj(_,other) if handle.same_object(other))).ok_or("objeto de otro heap")
}
// Resuelve un campo de referencia mientras el llamador posee el heap. Solo
// convierte objetos ordinarios del mismo heap; no expone índices ni convierte
// arrays, String u otras representaciones especiales. No mantiene el lock al
// acceder al destino: es seguro también con autoalias y ciclos.
fn shared_object_reference(h:&mut Heap,owner:&NumericObjectHandle,slot:usize)->Result<Option<NumericObjectHandle>,&'static str>{
    resolve_shared_object(h,owner)?;
    let target={
        let fields=owner.fields.lock().map_err(|_|"objeto compartido dañado")?;
        match fields.get(slot){Some(V::R(id))=>*id,Some(_)=>return Err("campo no referencia"),None=>return Err("campo inexistente")}
    };
    match target{None=>Ok(None),Some(id)=>share_project_object(h,id).map(Some)}
}

// Formas válidas de dup_x1, dup_x2, dup2_x1 y dup2_x2 según categoría JVM.
fn stack_dup_x(s:&mut Vec<V>,op:u8) {
    fn cat1(v:V)->bool {!matches!(v,V::L(_)|V::D(_))}
    let v1=s.pop().expect("pila vacía");
    let v2=s.pop().expect("pila vacía");
    match op {
        0x5a => {assert!(cat1(v1)&&cat1(v2),"dup_x1 inválido");s.extend([v1,v2,v1]);}
        0x5b => {assert!(cat1(v1),"dup_x2 inválido");if cat1(v2){let v3=s.pop().expect("pila vacía");assert!(cat1(v3),"dup_x2 inválido");s.extend([v1,v3,v2,v1]);}else{s.extend([v1,v2,v1]);}}
        0x5d => {if cat1(v1){assert!(cat1(v2),"dup2_x1 inválido");let v3=s.pop().expect("pila vacía");assert!(cat1(v3),"dup2_x1 inválido");s.extend([v2,v1,v3,v2,v1]);}else{assert!(cat1(v2),"dup2_x1 inválido");s.extend([v1,v2,v1]);}}
        0x5e => {if cat1(v1){assert!(cat1(v2),"dup2_x2 inválido");let v3=s.pop().expect("pila vacía");if cat1(v3){let v4=s.pop().expect("pila vacía");assert!(cat1(v4),"dup2_x2 inválido");s.extend([v2,v1,v4,v3,v2,v1]);}else{s.extend([v2,v1,v3,v2,v1]);}}else if cat1(v2){let v3=s.pop().expect("pila vacía");assert!(cat1(v3),"dup2_x2 inválido");s.extend([v1,v3,v2,v1]);}else{s.extend([v1,v2,v1]);}}
        _=>panic!("operación dup no soportada"),
    }
}

// Equivalentes monohilo acotados: ConcurrentHashMap con claves String y LinkedBlockingQueue.
fn collection_new(h:&mut Heap,class:&str)->usize {
    if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}
    let value=match class {"java/util/concurrent/ConcurrentHashMap"=>Array::Map(Vec::new(),0,false),"java/util/concurrent/LinkedBlockingQueue"=>Array::Queue(std::collections::VecDeque::new()),"java/util/concurrent/ConcurrentLinkedQueue"=>Array::ConcurrentQueue(std::collections::VecDeque::new()),"java/util/ArrayDeque"=>Array::Deque(std::collections::VecDeque::new()),"java/util/ArrayList"=>Array::List(Vec::new(),0),"java/util/LinkedHashSet"=>Array::Set(Vec::new(),0),"java/util/HashSet"=>Array::HashSet(Vec::new(),0),_=>panic!("colección no soportada")};
    let id=h.arrays.len();h.arrays.push(value);id
}
// KeySetView monohilo sin concurrencia ni iteración; claves String o Class.
fn concurrent_keyset_new(h:&mut Heap)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::KeySet(Vec::new(),0));id}
fn linked_set_capacity(h:&mut Heap,r:Option<usize>,n:i32){collection_init(h,r,"java/util/LinkedHashSet");if n<0{let message=new_string(h,format!("Illegal initial capacity: {n}").encode_utf16().collect());let ex=new_exception(h,"IllegalArgumentException");init_exception(h,Some(ex),"IllegalArgumentException",Some(message));throw_ref(h,Some(ex));}if n>1_000_000{error("LinkedHashSet: capacidad experimental excedida");}}
fn collection_init(h:&Heap,r:Option<usize>,class:&str){let id=array_id(h,r);if !matches!((class,&h.arrays[id]),("java/util/concurrent/ConcurrentHashMap",Array::Map(_,_,_))|("java/util/concurrent/LinkedBlockingQueue",Array::Queue(_))|("java/util/concurrent/ConcurrentLinkedQueue",Array::ConcurrentQueue(_))|("java/util/ArrayDeque",Array::Deque(_))|("java/util/ArrayList",Array::List(_,_))|("java/util/LinkedHashSet",Array::Set(_,_))|("java/util/HashSet",Array::HashSet(_,_))){panic!("constructor de colección incompatible")}}
fn immutable_list_new(h:&mut Heap,v:Vec<Option<usize>>)->usize{if v.iter().any(Option::is_none){raise("NullPointerException","");}if v.is_empty(){if let Some(id)=h.immutable_empty{return id;}}if h.arrays.len()>=10000||h.elements.checked_add(v.len()).map_or(true,|n|n>1_000_000){error("Límite experimental de heap excedido");}let empty=v.is_empty();h.elements+=v.len();let id=h.arrays.len();h.arrays.push(Array::ImmutableList(v));if empty{h.immutable_empty=Some(id);}id}
fn immutable_list_from_array(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);let values=match &h.arrays[id]{Array::Strings(v)|Array::Refs(_,v)|Array::ProjectRefs(_,v)=>v.clone(),_=>error("List.of: array de referencia no soportado")};immutable_list_new(h,values)}
fn standardlevel_enumset(h:&mut Heap,class:Option<usize>,slot:usize)->usize{let cid=array_id(h,class);if !matches!(h.arrays[cid],Array::Class("org/apache/logging/log4j/spi/StandardLevel")){error("EnumSet.allOf: clase fuera del perfil");}let arr=match h.fields.get(slot){Some(V::R(Some(a)))=>*a,_=>error("EnumSet.allOf: valores aún no preparados")};let values=match &h.arrays[arr]{Array::ProjectRefs("org/apache/logging/log4j/spi/StandardLevel",v)=>v.iter().map(|v|v.unwrap_or_else(||error("EnumSet.allOf: valor nulo"))).collect::<Vec<_>>(),_=>error("EnumSet.allOf: array incompatible")};for (i,id) in values.iter().enumerate(){if h.enum_values.get(id).map(|(_,n)|*n)!=Some(i as i32){error("EnumSet.allOf: ordinal inconsistente");}}if h.arrays.len()>=10000||h.elements.saturating_add(values.len())>1_000_000{error("Límite experimental de heap excedido");}h.elements+=values.len();let out=h.arrays.len();h.arrays.push(Array::EnumSet(values));out}
fn empty_list(h:&mut Heap)->usize{if let Some(id)=h.empty_list{return id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::EmptyList);h.empty_list=Some(id);id}
fn empty_set(h:&mut Heap)->usize{if let Some(id)=h.empty_set{return id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::EmptySet);h.empty_set=Some(id);id}
fn empty_iterator(h:&mut Heap)->usize{if let Some(id)=h.empty_iterator{return id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::EmptyIterator);h.empty_iterator=Some(id);id}
fn empty_map(h:&mut Heap)->usize{if let Some(id)=h.empty_map{return id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::EmptyMap);h.empty_map=Some(id);id}
fn tree_new(h:&mut Heap)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::TreeMap(Vec::new(),0));id}
fn tree_id(h:&Heap,r:Option<usize>)->usize{let id=array_id(h,r);if !matches!(h.arrays[id],Array::TreeMap(_,_)){error("TreeMap concreto no soportado");}id}
fn tree_compare(h:&Heap,a:usize,b:usize)->std::cmp::Ordering{match (&h.arrays[a],&h.arrays[b]){(Array::Character(x),Array::Character(y))=>x.cmp(y),(Array::Str(x),Array::Str(y))=>x.cmp(y),(Array::Character(_),Array::Str(_))|(Array::Str(_),Array::Character(_))=>raise("ClassCastException",""),_=>error("TreeMap: solo claves Character/String")}}
fn tree_key(h:&Heap,k:Option<usize>)->usize{let id=k.unwrap_or_else(||raise("NullPointerException",""));if !matches!(h.arrays.get(id),Some(Array::Character(_)|Array::Str(_))){error("TreeMap: solo claves Character/String");}id}
fn tree_search(h:&Heap,id:usize,key:Option<usize>)->Result<usize,usize>{let k=tree_key(h,key);match &h.arrays[id]{Array::TreeMap(v,_)=>v.binary_search_by(|(other,_)|tree_compare(h,*other,k)),_=>unreachable!()}}
fn tree_entry_set(h:&mut Heap,r:Option<usize>)->usize{let id=tree_id(h,r);if let Some(x)=h.tree_entry_views.get(&id){return *x;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let view=h.arrays.len();h.arrays.push(Array::TreeEntries(id));h.tree_entry_views.insert(id,view);view}
fn tree_entry_instance(h:&Heap,r:Option<usize>)->bool{matches!(r.and_then(|id|h.arrays.get(id)),Some(Array::TreeEntry(_,_,_)))}
fn tree_entry_key(h:&Heap,r:Option<usize>)->Option<usize>{let id=array_id(h,r);let (map,key,version)=match h.arrays[id]{Array::TreeEntry(m,k,v)=>(m,k,v),_=>error("Map.Entry concreto no soportado")};let actual=match h.arrays[map]{Array::TreeMap(_,v)=>v,_=>unreachable!()};if version!=actual{error("Map.Entry tras modificación estructural no soportada");}Some(key)}
fn tree_entry_value(h:&Heap,r:Option<usize>)->Option<usize>{let id=array_id(h,r);let (map,key,version)=match h.arrays[id]{Array::TreeEntry(m,k,v)=>(m,k,v),_=>error("Map.Entry concreto no soportado")};let actual=match h.arrays[map]{Array::TreeMap(_,v)=>v,_=>unreachable!()};if version!=actual{error("Map.Entry tras modificación estructural no soportada");}let index=tree_search(h,map,Some(key)).unwrap_or_else(|_|error("entrada TreeMap inexistente"));match &h.arrays[map]{Array::TreeMap(v,_)=>v[index].1,_=>unreachable!()}}
fn linked_map_new(h:&mut Heap)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::LinkedMap(Vec::new(),0));id}
fn linked_map_id(h:&Heap,r:Option<usize>)->usize{let id=array_id(h,r);if !matches!(h.arrays[id],Array::LinkedMap(_,_)){error("LinkedHashMap concreto no soportado");}id}
fn hashmap_new(h:&mut Heap)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::HashMap(Vec::new()));id}
fn hashmap_id(h:&Heap,r:Option<usize>)->usize{let id=array_id(h,r);if !matches!(h.arrays[id],Array::HashMap(_)){error("HashMap concreto no soportado");}id}
fn hashmap_init_capacity(h:&mut Heap,r:Option<usize>,n:i32){hashmap_id(h,r);if n<0{let message=new_string(h,format!("Illegal initial capacity: {n}").encode_utf16().collect());let ex=new_exception(h,"IllegalArgumentException");init_exception(h,Some(ex),"IllegalArgumentException",Some(message));throw_ref(h,Some(ex));}if n>1_000_000{error("HashMap: capacidad experimental excedida");}}
fn hashmap_init_map(h:&Heap,r:Option<usize>,source:Option<usize>){hashmap_id(h,r);let id=map_id(h,source);if map_size(h,Some(id))!=0{error("HashMap(Map): copia no vacía no soportada");}}
fn hashmap_key_ok(h:&Heap,key:Option<usize>){if let Some(id)=key{if !matches!(h.arrays.get(id),Some(Array::Str(_)|Array::Class(_)))&&!h.enum_values.contains_key(&id){error("HashMap: solo claves String, Class, enum o null");}}}
fn hashmap_pos(h:&Heap,id:usize,key:Option<usize>)->Option<usize>{hashmap_key_ok(h,key);let entries=match &h.arrays[id]{Array::HashMap(v)|Array::LinkedMap(v,_)=>v,_=>unreachable!()};entries.iter().position(|(k,_)|match (*k,key){(None,None)=>true,(Some(a),Some(b)) if a==b=>true,(Some(a),Some(b))=>matches!((&h.arrays[a],&h.arrays[b]),(Array::Str(x),Array::Str(y)) if x==y),_=>false})}
// IdentityHashMap usa referencias (incluido null), no equals/hashCode.
fn identity_map_new(h:&mut Heap)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::IdentityMap(Vec::new()));id}
fn identity_map_id(h:&Heap,r:Option<usize>)->usize{let id=array_id(h,r);if !matches!(h.arrays[id],Array::IdentityMap(_)){error("IdentityHashMap: receptor incompatible");}id}
fn identity_pos(h:&Heap,id:usize,key:Option<usize>)->Option<usize>{match &h.arrays[id]{Array::IdentityMap(v)=>v.iter().position(|(k,_)|*k==key),_=>error("IdentityHashMap: receptor incompatible")}}
fn identity_set_new(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);let entries=match &h.arrays[id]{Array::IdentityMap(v)=>v,_=>error("newSetFromMap: solo IdentityHashMap soportado")};if !entries.is_empty(){raise("IllegalArgumentException","Map is non-empty");}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let out=h.arrays.len();h.arrays.push(Array::IdentitySet(id));out}
fn map_id(h:&Heap,r:Option<usize>)->usize {let id=array_id(h,r);if !matches!(h.arrays[id],Array::Map(_,_,_)|Array::HashMap(_)|Array::IdentityMap(_)|Array::LinkedMap(_,_)|Array::TreeMap(_,_)|Array::EmptyMap){error("Map concreto no soportado");}id}
fn queue_id(h:&Heap,r:Option<usize>)->usize {let id=array_id(h,r);if !matches!(h.arrays[id],Array::Queue(_)|Array::ConcurrentQueue(_)|Array::Deque(_)){error("Queue concreta no soportada");}id}
fn map_position(h:&Heap,id:usize,key:Option<usize>)->Option<usize> {
    let key=key.unwrap_or_else(||raise("NullPointerException",""));
    let units=match h.arrays.get(key){Some(Array::Str(v))=>v,_=>error("clave de ConcurrentHashMap no soportada: solo String")};
    match &h.arrays[id] {Array::Map(entries,_,_)=>entries.iter().position(|(k,_)|matches!(&h.arrays[*k],Array::Str(v) if v==units)),_=>unreachable!()}
}
fn map_get(h:&Heap,r:Option<usize>,key:Option<usize>)->Option<usize> {
    let id=map_id(h,r);if let Array::IdentityMap(v)=&h.arrays[id]{return identity_pos(h,id,key).and_then(|i|v[i].1);}if matches!(h.arrays[id],Array::EmptyMap){return None;}if matches!(h.arrays[id],Array::HashMap(_)|Array::LinkedMap(_,_)){let pos=hashmap_pos(h,id,key);return match &h.arrays[id]{Array::HashMap(v)|Array::LinkedMap(v,_)=>pos.and_then(|p|v[p].1),_=>unreachable!()};}if matches!(h.arrays[id],Array::TreeMap(_,_)){let pos=tree_search(h,id,key).ok();return match &h.arrays[id]{Array::TreeMap(v,_)=>pos.and_then(|p|v[p].1),_=>unreachable!()};}let pos=map_position(h,id,key);match &h.arrays[id]{Array::Map(v,_,_)=>pos.map(|i|v[i].1),_=>unreachable!()}
}
fn map_contains(h:&Heap,r:Option<usize>,key:Option<usize>)->bool{let id=map_id(h,r);if matches!(h.arrays[id],Array::IdentityMap(_)){return identity_pos(h,id,key).is_some();}if matches!(h.arrays[id],Array::EmptyMap){return false;}if matches!(h.arrays[id],Array::HashMap(_)|Array::LinkedMap(_,_)){return hashmap_pos(h,id,key).is_some();}if matches!(h.arrays[id],Array::TreeMap(_,_)){return tree_search(h,id,key).is_ok();}map_get(h,r,key).is_some()}
fn map_hash(h:&Heap,key:usize)->u32 {
    let units=string_units(h,Some(key));let mut hash=0u32;for c in units{hash=hash.wrapping_mul(31).wrapping_add(*c as u32);} (hash^(hash>>16))&0x7fffffff
}
fn map_resize(h:&mut Heap,id:usize,cap:usize){
    // CHM.transfer reutiliza el último tramo de cada cubeta y antepone en
    // orden inverso los nodos anteriores al dividir la tabla.
    let entries=match &h.arrays[id]{Array::Map(v,_,_)=>v.clone(),_=>unreachable!()};
    let mut bins=vec![Vec::new();cap];for pair in entries{let bin=map_hash(h,pair.0) as usize&(cap-1);bins[bin].push(pair);}
    let mut next=vec![Vec::new();cap*2];
    for (index,bin) in bins.into_iter().enumerate(){if bin.is_empty(){continue;}
        let mut last=0;let mut bit=(map_hash(h,bin[0].0) as usize)&cap;
        for i in 1..bin.len(){let b=(map_hash(h,bin[i].0) as usize)&cap;if b!=bit{bit=b;last=i;}}
        for pair in bin[..last].iter().rev(){let b=(map_hash(h,pair.0) as usize)&cap;next[index+b].push(*pair);}
        for pair in &bin[last..]{let b=(map_hash(h,pair.0) as usize)&cap;next[index+b].push(*pair);}
    }
    if let Array::Map(entries,table,_)=&mut h.arrays[id]{*entries=next.into_iter().flatten().collect();*table=cap*2;}
}
fn map_put(h:&mut Heap,r:Option<usize>,key:Option<usize>,value:Option<usize>,absent:bool)->Option<usize> {
    let id=map_id(h,r);if matches!(h.arrays[id],Array::IdentityMap(_)){let pos=identity_pos(h,id,key);if let Array::IdentityMap(v)=&mut h.arrays[id]{if let Some(i)=pos{let old=v[i].1;if !absent||old.is_none(){v[i].1=value;}return old;}if h.elements>=1_000_000{error("Límite experimental de heap excedido");}h.elements+=1;v.push((key,value));return None;}unreachable!()}if matches!(h.arrays[id],Array::EmptyMap){raise("UnsupportedOperationException","");}if h.active_maps.contains(&id){error("ConcurrentHashMap.computeIfAbsent: mutación reentrante no soportada");}if matches!(h.arrays[id],Array::LinkedMap(_,_)){let pos=hashmap_pos(h,id,key);if let Array::LinkedMap(entries,version)=&mut h.arrays[id]{if let Some(i)=pos{let old=entries[i].1;if !absent||old.is_none(){entries[i].1=value;}return old;}if h.elements>=1_000_000{error("Límite experimental de heap excedido");}h.elements+=1;entries.push((key,value));*version=version.wrapping_add(1);return None;}unreachable!()}if matches!(h.arrays[id],Array::TreeMap(_,_)){let search=tree_search(h,id,key);let key=key.unwrap();if let Array::TreeMap(entries,version)=&mut h.arrays[id]{match search{Ok(i)=>{let old=entries[i].1;if !absent||old.is_none(){entries[i].1=value;}return old;},Err(i)=>{if h.elements>=1_000_000{error("Límite experimental de heap excedido");}h.elements+=1;entries.insert(i,(key,value));*version=version.wrapping_add(1);return None;}}}unreachable!()}if matches!(h.arrays[id],Array::HashMap(_)){let pos=hashmap_pos(h,id,key);if let Array::HashMap(entries)=&mut h.arrays[id]{if let Some(i)=pos{let old=entries[i].1;if !absent||old.is_none(){entries[i].1=value;}return old;}if h.elements>=1_000_000{error("Límite experimental de heap excedido");}h.elements+=1;entries.push((key,value));return None;}unreachable!()}let v=value.unwrap_or_else(||raise("NullPointerException",""));let pos=map_position(h,id,key);
    if let Some(i)=pos {if let Array::Map(entries,_,_)=&mut h.arrays[id]{let old=entries[i].1;if !absent{entries[i].1=v;}return Some(old);}unreachable!()}
    if h.elements>=1_000_000{error("Límite experimental de heap excedido");}h.elements+=1;
    let k=key.unwrap();let (cap,collisions,position)=match &h.arrays[id]{Array::Map(entries,cap,_)=>{let cap=if *cap==0{16}else{*cap};let bin=map_hash(h,k) as usize&(cap-1);let position=entries.iter().position(|(old,_)|map_hash(h,*old) as usize&(cap-1)>bin).unwrap_or(entries.len());(cap,entries.iter().filter(|(old,_)|map_hash(h,*old) as usize&(cap-1)==bin).count(),position)},_=>unreachable!()};
    let resize=if let Array::Map(entries,table,complex)=&mut h.arrays[id]{entries.insert(position,(k,v));*table=cap;if collisions>=8{*complex=true;}entries.len()>=cap-cap/4}else{false};
    if resize{map_resize(h,id,cap);}None
}
fn map_compute(h:&mut Heap,r:Option<usize>,key:Option<usize>,fun:Option<usize>,callback:fn(&mut Heap,Option<usize>,Option<usize>)->Option<usize>)->Option<usize>{
    let id=map_id(h,r);if matches!(h.arrays[id],Array::IdentityMap(_)){error("IdentityHashMap.computeIfAbsent: no soportado");}if matches!(h.arrays[id],Array::EmptyMap){raise("UnsupportedOperationException","");}if fun.is_none()||(key.is_none()&&!matches!(h.arrays[id],Array::HashMap(_)|Array::LinkedMap(_,_))){raise("NullPointerException","");}if let Some(v)=map_get(h,r,key){return Some(v);}if h.active_maps.contains(&id){error("ConcurrentHashMap.computeIfAbsent: llamada reentrante no soportada");}
    h.active_maps.push(id);let result=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||{let _opaque=call_guard("<jdk-callback>");callback(h,fun,key)}));h.active_maps.pop();let v=match result{Ok(v)=>v,Err(p)=>std::panic::resume_unwind(p)};if v.is_some(){map_put(h,r,key,v,true);}v
}
fn map_values(h:&mut Heap,r:Option<usize>)->usize{let id=map_id(h,r);if matches!(h.arrays[id],Array::IdentityMap(_)){error("IdentityHashMap.values: vista no soportada");}if let Some(v)=h.map_views.get(&id){return *v;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let view=h.arrays.len();h.arrays.push(Array::MapValues(id));h.map_views.insert(id,view);view}
fn map_values_snapshot(h:&Heap,id:usize)->Vec<Option<usize>> {
    if matches!(h.arrays[id],Array::EmptyMap){return Vec::new();}if let Array::TreeMap(entries,_)=&h.arrays[id]{return entries.iter().map(|(_,v)|*v).collect();}if let Array::LinkedMap(entries,_)=&h.arrays[id]{return entries.iter().map(|(_,v)|*v).collect();}if let Array::HashMap(entries)=&h.arrays[id]{if entries.len()>1{error("HashMap.values: orden no verificado para varios elementos");}return entries.iter().map(|(_,v)|*v).collect();}let (entries,cap,complex)=match &h.arrays[id]{Array::Map(v,c,x)=>(v,*c,*x),_=>panic!("Map inválido")};if complex{error("ConcurrentHashMap.values: colisiones complejas no soportadas");}
    entries.iter().map(|(_,v)|Some(*v)).collect()
}
fn list_construct_capacity(h:&Heap,r:Option<usize>,n:i32){list_id(h,r);if n<0{raise("IllegalArgumentException","");}if n>1_000_000{error("ArrayList: capacidad experimental excedida");}}
fn list_sort_strings(h:&mut Heap,r:Option<usize>){let id=list_id(h,r);let mut values=match &h.arrays[id]{Array::List(v,_)=>v.clone(),_=>error("Collections.sort: solo ArrayList")};if values.len()>1{for v in &values{let value=v.unwrap_or_else(||raise("NullPointerException",""));if !matches!(h.arrays[value],Array::Str(_)){error("Collections.sort: solo String")}}values.sort_by(|a,b|string_units(h,*a).cmp(string_units(h,*b)));}if let Array::List(v,version)=&mut h.arrays[id]{*v=values;*version=version.wrapping_add(1);}}
fn collection_add_all(h:&mut Heap,target:Option<usize>,source:Option<usize>)->bool{let id=array_id(h,target);let src=array_id(h,source);if let Array::IdentitySet(_)=h.arrays[id]{let values=match &h.arrays[src]{Array::IdentitySet(map)=>match &h.arrays[*map]{Array::IdentityMap(v)=>v.iter().map(|(k,_)|*k).collect::<Vec<_>>(),_=>unreachable!()},Array::List(v,_)|Array::ImmutableList(v)=>v.clone(),Array::EmptyList|Array::EmptySet=>Vec::new(),_=>error("IdentitySet.addAll: fuente fuera del perfil")};let mut changed=false;for v in values{changed|=collection_add(h,Some(id),v);}return changed;}let values=match &h.arrays[src]{Array::List(v,_)|Array::Set(v,_)|Array::ImmutableList(v)=>v.clone(),Array::ArraysList(a)=>match &h.arrays[*a]{Array::Strings(v)|Array::Refs(_,v)|Array::ProjectRefs(_,v)=>v.clone(),_=>unreachable!()},Array::Queue(v)|Array::ConcurrentQueue(v)|Array::Deque(v)=>v.iter().copied().map(Some).collect(),Array::EmptyList|Array::EmptySet=>Vec::new(),Array::MapValues(map)=>map_values_snapshot(h,*map),_=>error("addAll: colección fuente no soportada")};if matches!(h.arrays[id],Array::ImmutableList(_)){raise("UnsupportedOperationException","");}if matches!(h.arrays[id],Array::EmptyList|Array::EmptySet|Array::ArraysList(_)){if values.is_empty(){return false;}raise("UnsupportedOperationException","");}if !matches!(h.arrays[id],Array::List(_,_)){error("addAll: colección destino no soportada");}if h.elements.checked_add(values.len()).map_or(true,|n|n>1_000_000){error("Límite experimental de heap excedido");}let changed=!values.is_empty();h.elements+=values.len();if let Array::List(v,version)=&mut h.arrays[id]{*version=version.wrapping_add(1);v.extend(values);}changed}
fn list_construct_collection(h:&mut Heap,r:Option<usize>,collection:Option<usize>){
    let id=list_id(h,r);let source=array_id(h,collection);let values=match &h.arrays[source]{Array::List(v,_)|Array::Set(v,_)|Array::ImmutableList(v)=>v.clone(),Array::ArraysList(a)=>match &h.arrays[*a]{Array::Strings(v)|Array::Refs(_,v)|Array::ProjectRefs(_,v)=>v.clone(),_=>unreachable!()},Array::Queue(v)|Array::ConcurrentQueue(v)|Array::Deque(v)=>v.iter().copied().map(Some).collect(),Array::EmptyList|Array::EmptySet=>Vec::new(),Array::MapValues(map)=>map_values_snapshot(h,*map),_=>error("ArrayList(Collection): colección no soportada")};
    if h.elements.checked_add(values.len()).map_or(true,|n|n>1_000_000){error("Límite experimental de heap excedido");}h.elements+=values.len();
    if let Array::List(v,_)=&mut h.arrays[id]{*v=values;}
}
fn map_remove(h:&mut Heap,r:Option<usize>,key:Option<usize>)->Option<usize> {
    let id=map_id(h,r);if matches!(h.arrays[id],Array::IdentityMap(_)){let pos=identity_pos(h,id,key);return match &mut h.arrays[id]{Array::IdentityMap(v)=>pos.and_then(|i|v.remove(i).1),_=>unreachable!()};}if matches!(h.arrays[id],Array::EmptyMap){return None;}if h.active_maps.contains(&id){error("ConcurrentHashMap.computeIfAbsent: mutación reentrante no soportada");}if matches!(h.arrays[id],Array::LinkedMap(_,_)){let pos=hashmap_pos(h,id,key);return match &mut h.arrays[id]{Array::LinkedMap(v,version)=>pos.and_then(|p|{*version=version.wrapping_add(1);v.remove(p).1}),_=>unreachable!()};}if matches!(h.arrays[id],Array::TreeMap(_,_)){let pos=tree_search(h,id,key).ok();return match &mut h.arrays[id]{Array::TreeMap(v,version)=>pos.and_then(|p|{*version=version.wrapping_add(1);v.remove(p).1}),_=>unreachable!()};}if matches!(h.arrays[id],Array::HashMap(_)){let pos=hashmap_pos(h,id,key);return match &mut h.arrays[id]{Array::HashMap(v)=>pos.and_then(|p|v.remove(p).1),_=>unreachable!()};}let pos=map_position(h,id,key);match &mut h.arrays[id] {Array::Map(v,_,_)=>pos.map(|i|v.remove(i).1),_=>unreachable!()}
}
fn map_size(h:&Heap,r:Option<usize>)->i32 {let id=map_id(h,r);match &h.arrays[id]{Array::Map(v,_,_)=>v.len() as i32,Array::HashMap(v)|Array::IdentityMap(v)|Array::LinkedMap(v,_)=>v.len() as i32,Array::TreeMap(v,_)=>v.len() as i32,Array::EmptyMap=>0,_=>unreachable!()}}
fn map_clear(h:&mut Heap,r:Option<usize>){let id=map_id(h,r);if h.active_maps.contains(&id){error("ConcurrentHashMap.computeIfAbsent: mutación reentrante no soportada");}match &mut h.arrays[id]{Array::Map(v,_,_)=>v.clear(),Array::HashMap(v)|Array::IdentityMap(v)=>v.clear(),Array::LinkedMap(v,version)=>{v.clear();*version=version.wrapping_add(1)},Array::TreeMap(v,version)=>{v.clear();*version=version.wrapping_add(1)},Array::EmptyMap=>{},_=>unreachable!()}}
fn queue_offer(h:&mut Heap,r:Option<usize>,value:Option<usize>){let id=queue_id(h,r);let v=value.unwrap_or_else(||raise("NullPointerException",""));if h.elements>=1_000_000{error("Límite experimental de heap excedido");}h.elements+=1;match &mut h.arrays[id]{Array::Queue(q)|Array::ConcurrentQueue(q)|Array::Deque(q)=>q.push_back(v),_=>unreachable!()}}
fn queue_poll(h:&mut Heap,r:Option<usize>,remove:bool)->Option<usize>{let id=queue_id(h,r);match &mut h.arrays[id]{Array::Queue(q)|Array::ConcurrentQueue(q)|Array::Deque(q)=>if remove {q.pop_front()}else{q.front().copied()},_=>unreachable!()}}
fn deque_add_first(h:&mut Heap,r:Option<usize>,value:Option<usize>){let id=queue_id(h,r);let value=value.unwrap_or_else(||raise("NullPointerException",""));if h.elements>=1_000_000{error("Límite experimental de heap excedido");}h.elements+=1;match &mut h.arrays[id]{Array::Deque(v)=>v.push_front(value),_=>error("Deque concreto no soportado")}}
fn deque_take(h:&mut Heap,r:Option<usize>,first:bool,required:bool)->Option<usize>{let id=queue_id(h,r);let val=match &mut h.arrays[id]{Array::Deque(v)=>if first{v.pop_front()}else{v.pop_back()},_=>error("Deque concreto no soportado")};if required&&val.is_none(){raise("NoSuchElementException","");}val}
fn queue_drain_to(h:&mut Heap,r:Option<usize>,dst:Option<usize>,max:i32)->i32{
    let src=queue_id(h,r);let target=array_id(h,dst);if src==target{raise("IllegalArgumentException","");}if max<=0{return 0;}
    let mut count=0;while count<max{let value=queue_poll(h,Some(src),false);if value.is_none(){break;}
        if matches!(h.arrays[target],Array::MapValues(_)){raise("UnsupportedOperationException","");}collection_add(h,Some(target),value);queue_poll(h,Some(src),true);count+=1;
    }count
}
fn queue_size(h:&Heap,r:Option<usize>)->i32{let id=queue_id(h,r);match &h.arrays[id]{Array::Queue(q)|Array::ConcurrentQueue(q)|Array::Deque(q)=>q.len() as i32,_=>unreachable!()}}
fn queue_clear(h:&mut Heap,r:Option<usize>){let id=queue_id(h,r);match &mut h.arrays[id]{Array::Queue(q)|Array::ConcurrentQueue(q)|Array::Deque(q)=>q.clear(),_=>unreachable!()}}

// ThreadLocal exacto por defecto en un único hilo; sin subclases ni withInitial.
fn threadlocal_new(h:&mut Heap)->usize {if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Local(None));id}
fn threadlocal_id(h:&Heap,r:Option<usize>)->usize {let id=array_id(h,r);if !matches!(h.arrays[id],Array::Local(_)|Array::LocalObj(_,_,_)|Array::SuppliedLocal(_,_)){error("ThreadLocal concreto no soportado");}id}
fn threadlocal_with_initial(h:&mut Heap,supplier:Option<usize>)->usize {let supplier=supplier.unwrap_or_else(||raise("NullPointerException",""));if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::SuppliedLocal(supplier,None));id}
fn threadlocal_get(h:&mut Heap,r:Option<usize>,callback:fn(&mut Heap,Option<usize>)->Option<usize>)->Option<usize>{let id=threadlocal_id(h,r);match &h.arrays[id]{Array::Local(v)|Array::LocalObj(_,_,v)=>*v,Array::SuppliedLocal(_,Some(v))=>*v,Array::SuppliedLocal(supplier,None)=>{let supplier=*supplier;let value={let _opaque=call_guard("<jdk-callback>");callback(h,Some(supplier))};match &mut h.arrays[id]{Array::SuppliedLocal(_,state)=>*state=Some(value),_=>unreachable!()}value},_=>unreachable!()}}
fn threadlocal_set(h:&mut Heap,r:Option<usize>,v:Option<usize>){let id=threadlocal_id(h,r);match &mut h.arrays[id]{Array::Local(value)|Array::LocalObj(_,_,value)=>*value=v,Array::SuppliedLocal(_,state)=>*state=Some(v),_=>unreachable!()}}
fn threadlocal_remove(h:&mut Heap,r:Option<usize>){let id=threadlocal_id(h,r);match &mut h.arrays[id]{Array::Local(value)|Array::LocalObj(_,_,value)=>*value=None,Array::SuppliedLocal(_,state)=>*state=None,_=>unreachable!()}}

// Perfil de propiedades explícitas de SLF4J; otras propiedades JVM se rechazan, no se inventan.
// URI.create se restringe a los 23 literales válidos de CommonLinks 26.3.
fn uri_create_common_link(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);let text=String::from_utf16(string_units(h,r)).unwrap_or_else(|_|error("URI.create: fuera del perfil CommonLinks"));if !matches!(text.as_str(),"https://aka.ms/MinecraftGDPR"|"https://aka.ms/MinecraftEULA"|"http://go.microsoft.com/fwlink/?LinkId=521839"|"https://aka.ms/MinecraftJavaAttribution"|"https://aka.ms/MinecraftJavaLicenses"|"https://aka.ms/BuyMinecraftJava"|"https://aka.ms/JavaAccountSettings"|"https://aka.ms/snapshotfeedback?ref=game"|"https://aka.ms/javafeedback?ref=game"|"https://aka.ms/snapshotbugs?ref=game"|"https://aka.ms/Minecraft-Support"|"https://aka.ms/MinecraftJavaAccessibility"|"https://aka.ms/aboutjavareporting"|"https://aka.ms/mcjavamoderation"|"https://aka.ms/javablocking"|"https://aka.ms/MinecraftSymLinks"|"https://aka.ms/MinecraftJavaXboxPrivacyAndSafety"|"https://aka.ms/startjavarealmstrial"|"https://aka.ms/BuyJavaRealms"|"https://aka.ms/MinecraftRealmsTerms"|"https://aka.ms/MinecraftRealmsContentCreator"|"https://aka.ms/ExtendJavaRealms"|"https://bugs.mojang.com/browse/MCPE-28723"){error("URI.create: fuera del perfil CommonLinks");}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let out=h.arrays.len();h.arrays.push(Array::Uri(id));out}
fn uri_path(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);if let Some(v)=h.uri_paths.get(&id){return *v;}let text=match h.arrays[id]{Array::Uri(s)=>s,_=>error("URI.getPath: receptor fuera del perfil")};let units=string_units(h,Some(text));let colon=units.iter().position(|c|*c==58).unwrap_or_else(||error("URI.getPath: URI fuera del perfil CommonLinks"));if units.get(colon+1..colon+3)!=Some(&[47,47]){error("URI.getPath: autoridad fuera del perfil");}let after=colon+3;let start=units[after..].iter().position(|c|*c==47||*c==63||*c==35).map(|v|v+after).unwrap_or(units.len());let end=units[start..].iter().position(|c|*c==63||*c==35).map(|v|v+start).unwrap_or(units.len());let path=if units.get(start)==Some(&47){units[start..end].to_vec()}else{Vec::new()};if path.contains(&37){error("URI.getPath: escapes fuera del perfil");}let value=new_string(h,path);h.uri_paths.insert(id,value);value}
fn uri_scheme(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);if let Some(v)=h.uri_schemes.get(&id){return *v;}let text=match h.arrays[id]{Array::Uri(s)=>s,_=>error("URI.getScheme: receptor fuera del perfil")};let units=string_units(h,Some(text));let end=units.iter().position(|c|*c==58).unwrap_or_else(||error("URI.getScheme: URI fuera del perfil CommonLinks"));let scheme=units[..end].to_vec();let value=new_string(h,scheme);h.uri_schemes.insert(id,value);value}
fn uri_string(h:&Heap,r:Option<usize>)->usize{let id=array_id(h,r);match h.arrays[id]{Array::Uri(s)=>s,_=>error("URI concreta no soportada")}}
// java.util.Properties sin defaults; load(InputStream) usa ISO-8859-1 Java.
fn java_properties_new(h:&mut Heap)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Properties(std::collections::HashMap::new()));id}
fn java_properties_id(h:&Heap,r:Option<usize>)->usize{let id=array_id(h,r);if !matches!(h.arrays[id],Array::Properties(_)){error("Properties concreto no soportado");}id}
fn java_properties_entryset(h:&mut Heap,r:Option<usize>)->usize{let id=java_properties_id(h,r);if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let out=h.arrays.len();h.arrays.push(Array::PropertiesEntries(id));out}
fn properties_empty_iter(h:&Heap,id:usize){match &h.arrays[id]{Array::Properties(map) if map.is_empty()=>{},_=>error("Properties.entrySet: iteración no vacía o modificada no soportada")}}
fn java_properties_get(h:&Heap,r:Option<usize>,key:Option<usize>,fallback:Option<usize>)->Option<usize>{let id=java_properties_id(h,r);let key=string_units(h,key);match &h.arrays[id]{Array::Properties(map)=>map.get(key).copied().or(fallback),_=>unreachable!()}}
fn java_properties_set(h:&mut Heap,r:Option<usize>,key:Option<usize>,value:Option<usize>)->Option<usize>{let id=java_properties_id(h,r);let key=string_units(h,key).to_vec();let value=value.unwrap_or_else(||raise("NullPointerException",""));let _=string_units(h,Some(value));match &mut h.arrays[id]{Array::Properties(map)=>map.insert(key,value),_=>unreachable!()}}
fn properties_decode(units:&[u16])->Vec<u16>{let mut out=Vec::new();let mut i=0;while i<units.len(){let c=units[i];i+=1;if c!=92{out.push(c);continue;}if i>=units.len(){break;}let c=units[i];i+=1;match c{116=>out.push(9),114=>out.push(13),110=>out.push(10),102=>out.push(12),117=>{if i+4>units.len(){raise("IllegalArgumentException","Malformed \\uxxxx encoding.");}let mut x=0u16;for &v in &units[i..i+4]{let d=match v{48..=57=>v-48,65..=70=>v-65+10,97..=102=>v-97+10,_=>raise("IllegalArgumentException","Malformed \\uxxxx encoding.")};x=(x<<4)|d;}out.push(x);i+=4;},_=>out.push(c)}}out}
fn properties_load_line(h:&mut Heap,id:usize,line:&[u16]){
 let white=|c:u16|matches!(c,32|9|12);let mut end=0;let mut escaped=false;let mut separated=false;
 while end<line.len(){let c=line[end];if !escaped&&(c==61||c==58||white(c)){separated=c==61||c==58;break;}if c==92{escaped=!escaped}else{escaped=false;}end+=1;}
 let mut value=if separated{end+1}else{end};while value<line.len(){let c=line[value];if white(c){value+=1;continue;}if !separated&&(c==61||c==58){separated=true;value+=1;continue;}break;}
 let key=properties_decode(&line[..end]);let data=properties_decode(&line[value..]);let v=new_string(h,data);match &mut h.arrays[id]{Array::Properties(map)=>{map.insert(key,v);},_=>unreachable!()}
}
// Perfil estrictamente UTC y una propiedad eula=false; reloj real de sistema.
fn java_properties_store_eula(h:&mut Heap,r:Option<usize>,output:Option<usize>,comment:Option<usize>){
 let id=java_properties_id(h,r);let out=array_id(h,output);
 if std::env::var("MC_AOT_JAVA_TIMEZONE").as_deref()!=Ok("UTC")||std::env::var("TZ").as_deref()!=Ok("UTC"){error("Properties.store: requiere MC_AOT_JAVA_TIMEZONE=UTC y TZ=UTC");}
 if comment.is_none(){error("Properties.store: comentario fuera del perfil EULA");}let comment_units=string_units(h,comment);let expected="By changing the setting below to TRUE you are indicating your agreement to our EULA (https://aka.ms/MinecraftEULA).".encode_utf16().collect::<Vec<_>>();if comment_units!=expected{error("Properties.store: comentario fuera del perfil EULA");}
 let key="eula".encode_utf16().collect::<Vec<_>>();let val=match &h.arrays[id]{Array::Properties(map) if map.len()==1=>map.get(&key).copied(),_=>None};if val.is_none()||string_units(h,val)!="false".encode_utf16().collect::<Vec<_>>(){error("Properties.store: solo eula=false");}
 let seconds=std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_else(|_|error("Properties.store: reloj anterior a 1970")).as_secs();let days=seconds/86400;let rem=seconds%86400;
 // Gregorian civil date from days since Unix epoch, valid for the host clock range.
 let z=i64::try_from(days).unwrap_or_else(|_|error("Properties.store: fecha fuera de rango"))+719468;let era=z/146097;let doe=z-era*146097;let yoe=(doe-doe/1460+doe/36524-doe/146096)/365;let y=yoe+era*400;let doy=doe-(365*yoe+yoe/4-yoe/100);let mp=(5*doy+2)/153;let day=doy-(153*mp+2)/5+1;let month=mp+if mp<10{3}else{-9};let year=y+if month<=2{1}else{0};if !(1970..=9999).contains(&year){error("Properties.store: fecha fuera de rango");}
 let wd=["Sun","Mon","Tue","Wed","Thu","Fri","Sat"][(days as usize+4)%7];let mo=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][(month-1) as usize];let data=format!("#{}\n#{wd} {mo} {day:02} {:02}:{:02}:{:02} UTC {year}\neula=false\n",String::from_utf16(&expected).unwrap(),rem/3600,(rem%3600)/60,rem%60);
 match &mut h.arrays[out]{Array::FileOutput(file)=>{use std::io::Write;let file=file.as_mut().unwrap_or_else(||raise("IOException","Stream Closed"));if let Err(e)=file.write_all(data.as_bytes()){error(&format!("Properties.store: E/S no traducida: {e}"));}},_=>error("Properties.store: OutputStream concreto no soportado")}
}

fn java_properties_load(h:&mut Heap,r:Option<usize>,stream:Option<usize>){
 let id=java_properties_id(h,r);array_id(h,stream);let mut bytes=Vec::new();loop{let c=resource_read(h,stream);if c<0{break;}if bytes.len()>=1_048_576{error("Properties.load: archivo mayor que 1 MiB");}bytes.push(c as u8);}
 let mut pos=0usize;let mut logical=Vec::<u16>::new();let mut continuing=false;
 while pos<bytes.len(){let start=pos;while pos<bytes.len()&&!matches!(bytes[pos],b'\r'|b'\n'){pos+=1;}let end=pos;let terminated=pos<bytes.len();if terminated{let c=bytes[pos];pos+=1;if c==b'\r'&&pos<bytes.len()&&bytes[pos]==b'\n'{pos+=1;}}
  let mut begin=start;while begin<end&&matches!(bytes[begin],b' '|b'\t'|0x0c){begin+=1;}
  if !continuing&&(begin==end||matches!(bytes[begin],b'#'|b'!')){continue;}
  logical.extend(bytes[begin..end].iter().map(|x|*x as u16));let slashes=logical.iter().rev().take_while(|&&x|x==92).count();
  if slashes%2==1{logical.pop();if terminated{continuing=true;continue;}}
  properties_load_line(h,id,&logical);logical.clear();continuing=false;
 }
 if continuing||!logical.is_empty(){properties_load_line(h,id,&logical);}
}

fn property_allowed(k:&[u16])->bool {let log4j=k.len()>=5&&k[..5].iter().zip("log4j".encode_utf16()).all(|(a,b)|(*a|32)==(b|32));log4j||k.iter().copied().eq("max.bg.threads".encode_utf16())||k.starts_with(&[115,108,102,52,106,46])||k.starts_with(&[77,67,95,68,69,66,85,71,95])||k.starts_with(&[105,111,46,110,101,116,116,121,46])}
fn property_key(h:&Heap,r:Option<usize>)->Vec<u16> {
    let k=string_units(h,r).to_vec();if k.is_empty(){raise("IllegalArgumentException","");}
    if !property_allowed(&k){error("propiedad JVM no soportada: solo log4j*, slf4j.*, MC_DEBUG_*, io.netty.* o max.bg.threads");}k
}
fn properties_init(h:&mut Heap) {
    if h.properties.is_some(){return;}
    let mut result=std::collections::HashMap::new();
    let input=match std::env::var("MC_AOT_JAVA_PROPERTIES") {Ok(x)=>x,Err(std::env::VarError::NotPresent)=>String::new(),Err(_)=>error("MC_AOT_JAVA_PROPERTIES no es UTF-8")};
    for line in input.lines(){let (key,value)=line.split_once('=').unwrap_or_else(||error("MC_AOT_JAVA_PROPERTIES requiere líneas clave=valor"));let key=key.encode_utf16().collect::<Vec<_>>();if !property_allowed(&key){error("MC_AOT_JAVA_PROPERTIES: propiedad fuera del perfil explícito");}let v=new_string(h,value.encode_utf16().collect());result.insert(key,v);}
    h.properties=Some(result);
}
// Equivalente cerrado de PropertiesUtilsDouble Log4j 2.26.0 con recurso ausente
// comprobado y únicamente propiedades explícitas MC_AOT_JAVA_PROPERTIES.
fn status_normalize_units(units:&[u16])->Vec<u16>{let mut out=Vec::with_capacity(units.len());let mut i=0;while i<units.len(){let c=units[i];i+=1;if matches!(c,46|95|45){continue;}if c>127{if (0xd800..=0xdbff).contains(&c)&&i<units.len()&&(0xdc00..=0xdfff).contains(&units[i]){i+=1;}out.push(46);}else{out.push(if (65..=90).contains(&c){c+32}else{c});}}let prefix:Vec<u16>="log4j2".encode_utf16().collect();if out.starts_with(&prefix){out.remove(5);}out}
fn status_normalize_string(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);let src=string_units(h,r);let out=status_normalize_units(src);if out==src{return id;}new_string(h,out)}
fn status_normalize(k:&str)->Option<String>{if k.len()<5||!k.as_bytes()[..5].eq_ignore_ascii_case(b"log4j")||k.chars().any(|c|matches!(c,'\n'|'\r'|'\u{0085}'|'\u{2028}'|'\u{2029}')){return None;}String::from_utf16(&status_normalize_units(&k.encode_utf16().collect::<Vec<_>>())).ok()}
fn status_properties_map(h:&mut Heap)->usize{properties_init(h);let props=h.properties.as_ref().unwrap().iter().map(|(k,v)|(String::from_utf16(k).unwrap_or_else(|_|error("Log4j: clave no UTF-16 válida")),*v)).collect::<Vec<_>>();let map=hashmap_new(h);let mut seen=std::collections::HashSet::new();for (key,val) in props{if let Some(n)=status_normalize(&key){if !seen.insert(n.clone()){error("Log4j: claves de propiedad normalizadas duplicadas");}let k=new_string(h,n.encode_utf16().collect());map_put(h,Some(map),Some(k),Some(val),false);}}
 seen.clear();for (key,val) in std::env::vars_os(){let text=key.to_string_lossy();if let Some(n)=status_normalize(&text){if key.to_str().is_none(){error("Log4j: nombre de entorno no UTF-8");}if !seen.insert(n.clone()){error("Log4j: claves de entorno normalizadas duplicadas");}let value=val.to_str().unwrap_or_else(||error("Log4j: variable de entorno no UTF-8"));let key=new_string(h,n.encode_utf16().collect());let v=new_string(h,value.encode_utf16().collect());map_put(h,Some(map),Some(key),Some(v),false);}}map}
fn property_get(h:&mut Heap,k:Option<usize>)->Option<usize>{let key=property_key(h,k);properties_init(h);h.properties.as_ref().unwrap().get(&key).copied()}
fn property_set(h:&mut Heap,k:Option<usize>,v:Option<usize>)->Option<usize>{let key=property_key(h,k);let value=v.unwrap_or_else(||raise("NullPointerException",""));let _=string_units(h,Some(value));properties_init(h);h.properties.as_mut().unwrap().insert(key,value)}
fn property_clear(h:&mut Heap,k:Option<usize>)->Option<usize>{let key=property_key(h,k);properties_init(h);h.properties.as_mut().unwrap().remove(&key)}

// equalsIgnoreCase usa el fold simple Character.toLowerCase(toUpperCase(c)) de Java 25.
// Los pares sustitutos se comparan como puntos de código; sustitutos aislados se conservan.
fn string_upper_root_ascii(h:&mut Heap,r:Option<usize>,locale:Option<usize>)->usize{let id=array_id(h,r);let lid=array_id(h,locale);if !matches!(h.arrays[lid],Array::RootLocale){error("String.toUpperCase: solo Locale.ROOT");}let text=string_units(h,r);if text.iter().any(|c|*c>127){error("String.toUpperCase: solo ASCII ROOT");}let changed=text.iter().any(|c|*c>=97&&*c<=122);let units=text.iter().map(|c|if *c>=97&&*c<=122{*c-32}else{*c}).collect();if !changed{return id;}new_string(h,units)}
fn string_lower_root_ascii(h:&mut Heap,r:Option<usize>,locale:Option<usize>)->usize{let id=array_id(h,r);let lid=array_id(h,locale);if !matches!(h.arrays[lid],Array::RootLocale){error("String.toLowerCase: solo Locale.ROOT");}let text=string_units(h,r);if text.iter().any(|c|*c>127){error("String.toLowerCase: solo ASCII ROOT");}if !text.iter().any(|c|(65..=90).contains(c)){return id;}let units=text.iter().map(|c|if (65..=90).contains(c){*c+32}else{*c}).collect();new_string(h,units)}
fn string_lower_ascii(h:&mut Heap,r:Option<usize>)->usize{
    let id=array_id(h,r);let units=string_units(h,r);if units.iter().any(|c|*c>127){error("String.toLowerCase: Unicode no soportado");}
    let has_i=units.contains(&(b'I' as u16));let language=if has_i{match std::env::var("MC_AOT_JAVA_LANGUAGE"){Ok(v) if !v.is_empty()=>v, _=>error("String.toLowerCase: define MC_AOT_JAVA_LANGUAGE para I")}}else{String::new()};
    let special=matches!(language.as_str(),"tr"|"az");let mut out=Vec::with_capacity(units.len());let mut changed=false;
    for c in units {let lower=if *c==b'I' as u16&&special{0x0131}else if (65..=90).contains(c){*c+32}else{*c};changed|=lower!=*c;out.push(lower);}
    if !changed{id}else{new_string(h,out)}
}
fn string_trim(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);let units=string_units(h,r);let start=units.iter().position(|x|*x>32).unwrap_or(units.len());let end=units.iter().rposition(|x|*x>32).map(|i|i+1).unwrap_or(start);if start==0&&end==units.len(){return id;}if start==end{return string_literal(h,&[]);}let trimmed=units[start..end].to_vec();new_string(h,trimmed)}
fn string_equals_ignore_case(h:&Heap,a:Option<usize>,b:Option<usize>)->bool {
    let left=string_units(h,a);if b.is_none(){return false;}if a==b{return true;}
    let right=string_units(h,b);if left.len()!=right.len(){return false;}
    fn next(v:&[u16],p:&mut usize)->u32 {
        let hi=v[*p] as u32;*p+=1;
        if (0xd800..=0xdbff).contains(&hi) && *p<v.len() {let lo=v[*p] as u32;if (0xdc00..=0xdfff).contains(&lo){*p+=1;return 0x10000+((hi-0xd800)<<10)+(lo-0xdc00);}}
        hi
    }
    let (mut i,mut j)=(0,0);
    while i<left.len()&&j<right.len() {let x=next(left,&mut i);let y=next(right,&mut j);if x!=y && java25_casefold(x)!=java25_casefold(y){return false;}}
    i==left.len() && j==right.len()
}

// Literales Class internados sin inicializar la clase, y monitores de un único hilo.
fn class_literal(h:&mut Heap,name:&'static str)->usize {
    if let Some(id)=h.classes.get(name){return *id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}
    let id=h.arrays.len();h.arrays.push(Array::Class(name));h.classes.insert(name,id);id
}
// Las clases admitidas del JDK pertenecen al bootstrap; las del bundle comparten un loader.
// Este handle solo representa identidad: todavía no implementa carga ni recursos.
fn class_get_loader(h:&mut Heap,r:Option<usize>)->Option<usize> {
    let id=array_id(h,r);let name=match h.arrays[id] {Array::Class(n)=>n,_=>panic!("se esperaba Class")};
    if name.starts_with("java/")||matches!(name,"[Z"|"[B"|"[C"|"[S"|"[I"|"[J"|"[Ljava/lang/String;"|"[Ljava/lang/Class;"|"[Ljava/lang/Object;"){return None;}Some(app_class_loader(h))
}
fn platform_class_loader(h:&mut Heap)->usize{if let Some(id)=h.platform_loader{return id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::PlatformLoader);h.platform_loader=Some(id);id}
fn classloader_parent(h:&mut Heap,r:Option<usize>)->Option<usize>{let id=array_id(h,r);match h.arrays[id]{Array::AppLoader=>Some(platform_class_loader(h)),Array::PlatformLoader=>None,_=>error("ClassLoader.getParent: cargador fuera del perfil")}}
fn app_class_loader(h:&mut Heap)->usize{if let Some(id)=h.app_loader{return id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::AppLoader);h.app_loader=Some(id);id}
fn class_modifiers(h:&Heap,r:Option<usize>,registry:&[(&str,i32)])->i32{let id=array_id(h,r);let name=match h.arrays[id]{Array::Class(n)=>n,_=>error("Class.getModifiers: receptor fuera del perfil")};registry.iter().find(|(n,_)|*n==name).map(|(_,f)|*f).unwrap_or_else(||error("Class.getModifiers: clase fuera del registro"))}
fn class_is_array(h:&Heap,r:Option<usize>)->bool{let id=array_id(h,r);match h.arrays[id]{Array::Class(name)=>name.starts_with('['),_=>error("Class.isArray: receptor fuera del perfil")}}
fn class_get_name(h:&mut Heap,r:Option<usize>)->usize {
    let id=array_id(h,r);let name=match h.arrays[id]{Array::Class(n)=>n,_=>panic!("se esperaba Class")};
    let units:Vec<u16>=name.replace('/',".").encode_utf16().collect();string_literal(h,&units)
}
// Perfil monohilo: future completado normalmente, sin callbacks ni cancelación.
fn completed_future_new(h:&mut Heap,value:Option<usize>)->usize{if let Some(id)=value {let _=array_id(h,Some(id));}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::CompletedFuture(value));id}
fn completed_future_value(h:&Heap,r:Option<usize>)->Option<usize>{let id=array_id(h,r);match h.arrays[id]{Array::CompletedFuture(value)=>value,_=>error("CompletableFuture: solo completado normal del perfil")}}
// AtomicReference solo para ejecución monohilo; no proporciona memoria concurrente.
// Solo monohilo; la versión con contención requiere el heap concurrente futuro.
fn rw_lock_new(h:&mut Heap)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::ReadWriteLock(0,0,None,None));id}
fn rw_lock_id(h:&Heap,r:Option<usize>)->usize{let id=array_id(h,r);if !matches!(h.arrays[id],Array::ReadWriteLock(_,_,_,_)){error("ReadWriteLock concreto no soportado");}id}
fn rw_lock_view(h:&mut Heap,r:Option<usize>,read:bool)->usize{let id=rw_lock_id(h,r);let old=match h.arrays[id]{Array::ReadWriteLock(_,_,a,b)=>if read{a}else{b},_=>unreachable!()};if let Some(old)=old{return old;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let view=h.arrays.len();h.arrays.push(if read{Array::ReadLock(id)}else{Array::WriteLock(id)});if let Array::ReadWriteLock(_,_,a,b)=&mut h.arrays[id]{if read{*a=Some(view)}else{*b=Some(view)}}view}
fn reentrant_new(h:&mut Heap)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::ReentrantLock(0));id}
fn reentrant_count(h:&Heap,r:Option<usize>)->i32{let id=array_id(h,r);match h.arrays[id]{Array::ReentrantLock(n)=>n,_=>error("Lock concreto no soportado")}}
fn reentrant_lock(h:&mut Heap,r:Option<usize>){let id=array_id(h,r);match h.arrays[id]{Array::ReentrantLock(_)=>if let Array::ReentrantLock(n)=&mut h.arrays[id]{*n=n.checked_add(1).unwrap_or_else(||error("ReentrantLock: profundidad excedida"));},Array::ReadLock(parent)=>if let Array::ReadWriteLock(read,_,_,_)=&mut h.arrays[parent]{*read=read.checked_add(1).unwrap_or_else(||error("ReadLock: profundidad excedida"));},Array::WriteLock(parent)=>if let Array::ReadWriteLock(read,write,_,_)=&mut h.arrays[parent]{if *read>0&&*write==0{error("ReadWriteLock: upgrade bloquearía el hilo");}*write=write.checked_add(1).unwrap_or_else(||error("WriteLock: profundidad excedida"));},_=>error("Lock concreto no soportado")}}
fn reentrant_unlock(h:&mut Heap,r:Option<usize>){let id=array_id(h,r);let target=match h.arrays[id]{Array::ReentrantLock(_)=>(id,0),Array::ReadLock(p)=>(p,1),Array::WriteLock(p)=>(p,2),_=>error("Lock concreto no soportado")};let n=match (&mut h.arrays[target.0],target.1){(Array::ReentrantLock(n),0)=>n,(Array::ReadWriteLock(n,_,_,_),1)=>n,(Array::ReadWriteLock(_,n,_,_),2)=>n,_=>unreachable!()};if *n==0{raise("IllegalMonitorStateException","");}*n-=1;}
fn atomic_integer_new(h:&mut Heap)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::AtomicInteger(0));id}
fn atomic_integer_get(h:&Heap,r:Option<usize>)->i32{let id=array_id(h,r);match h.arrays[id]{Array::AtomicInteger(v)=>v,_=>error("AtomicInteger concreto no soportado")}}
fn atomic_integer_set(h:&mut Heap,r:Option<usize>,v:i32){let id=array_id(h,r);match &mut h.arrays[id]{Array::AtomicInteger(n)=>*n=v,_=>error("AtomicInteger concreto no soportado")}}
fn atomic_long_new(h:&mut Heap)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::AtomicLong(0));id}
fn atomic_long_get(h:&Heap,r:Option<usize>)->i64{let id=array_id(h,r);match h.arrays[id]{Array::AtomicLong(v)=>v,_=>error("AtomicLong concreto no soportado")}}
fn atomic_long_set(h:&mut Heap,r:Option<usize>,v:i64){let id=array_id(h,r);match &mut h.arrays[id]{Array::AtomicLong(n)=>*n=v,_=>error("AtomicLong concreto no soportado")}}
fn instant_now(h:&mut Heap)->usize{let total=match std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH){Ok(d)=>d.as_nanos() as i128,Err(e)=>-(e.duration().as_nanos() as i128)};let secs=i64::try_from(total.div_euclid(1_000_000_000)).unwrap_or_else(|_|error("reloj fuera de rango"));let nanos=total.rem_euclid(1_000_000_000) as i32;if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Instant(secs,nanos));id}
fn duration_between_instants(h:&mut Heap,a:Option<usize>,b:Option<usize>)->usize{let ai=array_id(h,a);let bi=array_id(h,b);let (as_,an)=match h.arrays[ai]{Array::Instant(s,n)=>(s,n),_=>error("Duration.between: solo Instant")};let (bs,bn)=match h.arrays[bi]{Array::Instant(s,n)=>(s,n),_=>error("Duration.between: solo Instant")};let total=(bs as i128-as_ as i128)*1_000_000_000+(bn as i128-an as i128);let sec=i64::try_from(total.div_euclid(1_000_000_000)).unwrap_or_else(|_|raise("ArithmeticException",""));let nano=total.rem_euclid(1_000_000_000) as i32;if sec==0&&nano==0{if let Some(id)=h.duration_zero{return id;}}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Duration(sec,nano));if sec==0&&nano==0{h.duration_zero=Some(id);}id}
fn atomic_ref_new(h:&mut Heap)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::AtomicRef(None));id}
fn atomic_ref_get(h:&Heap,r:Option<usize>)->Option<usize>{let id=array_id(h,r);match h.arrays[id]{Array::AtomicRef(v)=>v,_=>error("AtomicReference no soportada")}}
fn atomic_ref_set(h:&mut Heap,r:Option<usize>,v:Option<usize>){let id=array_id(h,r);match &mut h.arrays[id]{Array::AtomicRef(value)=>*value=v,_=>error("AtomicReference no soportada")}}
fn duration_from_millis(h:&mut Heap,m:i64)->usize{if m==0{if let Some(id)=h.duration_zero{return id;}}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Duration(m.div_euclid(1000),(m.rem_euclid(1000)*1_000_000) as i32));if m==0{h.duration_zero=Some(id);}id}
fn duration_parts(h:&Heap,r:Option<usize>)->(i64,i32){let id=array_id(h,r);match h.arrays[id]{Array::Duration(s,n)=>(s,n),_=>error("Duration concreto no soportado")}}
fn duration_nanos(h:&Heap,r:Option<usize>)->i64{let (s,n)=duration_parts(h,r);let value=(s as i128)*1_000_000_000i128+n as i128;i64::try_from(value).unwrap_or_else(|_|raise("ArithmeticException",""))}
fn duration_millis(h:&Heap,r:Option<usize>)->i64{let (s,n)=duration_parts(h,r);let value=((s as i128)*1_000_000_000+n as i128)/1_000_000;i64::try_from(value).unwrap_or_else(|_|raise("ArithmeticException",""))}
fn boolean_parse(h:&mut Heap,r:Option<usize>)->bool{if r.is_none(){return false;}let t=string_literal(h,&[116,114,117,101]);string_equals_ignore_case(h,r,Some(t))}
fn integer_parse(h:&Heap,r:Option<usize>)->i32{if r.is_none(){raise("NumberFormatException","");}let units=string_units(h,r);if units.iter().any(|x|*x>127){error("Integer.parseInt: dígitos Unicode no soportados");}let s=units.iter().map(|x|*x as u8 as char).collect::<String>();s.parse::<i32>().unwrap_or_else(|_|raise("NumberFormatException",""))}
fn integer_value_of(h:&mut Heap,n:i32)->usize{if (-128..=127).contains(&n){if let Some(id)=h.integers.get(&n){return *id;}}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Integer(n));if (-128..=127).contains(&n){h.integers.insert(n,id);}id}
fn long_value_of(h:&mut Heap,n:i64)->usize{if (-128..=127).contains(&n){if let Some(id)=h.longs.get(&n){return *id;}}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Long(n));if (-128..=127).contains(&n){h.longs.insert(n,id);}id}
fn long_value(h:&Heap,r:Option<usize>)->i64{let id=array_id(h,r);match h.arrays[id]{Array::Long(n)=>n,_=>error("Long concreto no soportado")}}
fn double_value_of(h:&mut Heap,n:f64)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Double(n));id}
fn double_value(h:&Heap,r:Option<usize>)->f64{let id=array_id(h,r);match h.arrays[id]{Array::Double(n)=>n,_=>error("Double concreto no soportado")}}
fn float_value_of(h:&mut Heap,n:f32)->usize{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Float(n));id}
fn float_value(h:&Heap,r:Option<usize>)->f32{let id=array_id(h,r);match h.arrays[id]{Array::Float(n)=>n,_=>error("Float concreto no soportado")}}
fn short_value_of(h:&mut Heap,n:i32)->usize{let n=n as i16;if (-128..=127).contains(&n){if let Some(id)=h.shorts.get(&n){return *id;}}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Short(n));if (-128..=127).contains(&n){h.shorts.insert(n,id);}id}
fn short_value(h:&Heap,r:Option<usize>)->i32{let id=array_id(h,r);match h.arrays[id]{Array::Short(n)=>n as i32,_=>error("Short concreto no soportado")}}
fn byte_value_of(h:&mut Heap,n:i32)->usize{let n=n as i8;if let Some(id)=h.bytes.get(&n){return *id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Byte(n));h.bytes.insert(n,id);id}
fn byte_value(h:&Heap,r:Option<usize>)->i32{let id=array_id(h,r);match h.arrays[id]{Array::Byte(n)=>n as i32,_=>error("Byte concreto no soportado")}}
fn integer_value(h:&Heap,r:Option<usize>)->i32{let id=array_id(h,r);match h.arrays[id]{Array::Integer(n)=>n,_=>error("Integer concreto no soportado")}}
fn boolean_value_of(h:&mut Heap,v:bool)->usize{let i=v as usize;if let Some(id)=h.booleans[i]{return id;}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Boolean(v));h.booleans[i]=Some(id);id}
fn boolean_value(h:&Heap,r:Option<usize>)->bool{let id=array_id(h,r);match h.arrays[id]{Array::Boolean(v)=>v,_=>error("Boolean concreto no soportado")}}
fn class_assertion_status(h:&Heap,r:Option<usize>)->bool{
    let id=array_id(h,r);let class=match h.arrays[id]{Array::Class(n)=>n,_=>panic!("Class inválida")};let binary=class.replace('/',".");
    let setting=match std::env::var("MC_AOT_ASSERTIONS"){Ok(s)=>s,Err(std::env::VarError::NotPresent)=>return false,Err(_)=>error("MC_AOT_ASSERTIONS no UTF-8")};
    setting.split(':').any(|item|item=="*"||item==binary)
}
fn class_assignable(h:&Heap,target:Option<usize>,source:Option<usize>,relations:&[(&str,&str)],types:&[&str])->bool{
    let tid=array_id(h,target);let sid=array_id(h,source);let t=match h.arrays[tid]{Array::Class(n)=>n,_=>panic!("Class inválida")};let s=match h.arrays[sid]{Array::Class(n)=>n,_=>panic!("Class inválida")};
    fn reference(s:&str)->bool{s.len()!=1 || !"VZBCSIJFD".contains(s)}
    fn is_project(s:&str)->bool{!s.starts_with('[')&&!["java/","javax/","jdk/","sun/","com/sun/"].iter().any(|p|s.starts_with(p))}
    fn component(s:&str)->Option<&str>{let x=s.strip_prefix('[')?;Some(if x.starts_with('L')&&x.ends_with(';'){&x[1..x.len()-1]}else{x})}
    fn eval(t:&str,s:&str,relations:&[(&str,&str)],types:&[&str])->bool{
        if t==s{return true;}if t=="java/lang/Object"&&reference(s){return true;}
        if s.starts_with('[') && matches!(t,"java/lang/Cloneable"|"java/io/Serializable"){return true;}
        if let Some(tc)=component(t){if let Some(sc)=component(s){return reference(tc)&&reference(sc)&&eval(tc,sc,relations,types);}return false;}
        if s.starts_with('['){return false;}
        if is_project(s){if !types.contains(&s){error("Class.isAssignableFrom: clase origen no registrada");}
            if is_project(t)||matches!(t,"java/lang/Runnable"|"java/lang/Cloneable"|"java/io/Serializable"){return relations.iter().any(|(source,target)|*source==s&&*target==t);}
            error("Class.isAssignableFrom: supertipo JDK no modelado");
        }
        if is_project(t){return false;}error("Class.isAssignableFrom: jerarquía JDK no modelada");
    }
    eval(t,s,relations,types)
}
fn class_as_subclass(h:&mut Heap,source:Option<usize>,target:Option<usize>,relations:&[(&str,&str)],types:&[&str],interfaces:&[&str])->usize {
    let id=array_id(h,source);array_id(h,target);if class_assignable(h,target,source,relations,types){return id;}
    let name=match h.arrays[id]{Array::Class(n)=>n,_=>error("Class.asSubclass: receptor fuera del perfil")};let jdk_interface=matches!(name,"java/lang/Runnable"|"java/lang/Cloneable"|"java/io/Serializable");let jdk_class=matches!(name,"java/lang/Object"|"java/lang/String"|"java/lang/Class"|"java/lang/Integer"|"java/lang/Long"|"java/lang/Boolean"|"java/lang/Byte"|"java/lang/Float");if ["java/","javax/","jdk/","sun/","com/sun/"].iter().any(|p|name.starts_with(p))&&!jdk_interface&&!jdk_class{error("Class.asSubclass: tipo JDK no modelado");}let prefix=if name.len()==1{""}else if jdk_interface||interfaces.contains(&name){"interface "}else{"class "};let message=new_string(h,format!("{prefix}{}",name.replace('/',".")).encode_utf16().collect());let ex=new_exception(h,"ClassCastException");init_exception(h,Some(ex),"ClassCastException",Some(message));throw_ref(h,Some(ex));
}
fn object_get_class(h:&mut Heap,r:Option<usize>)->usize {
    let id=array_id(h,r);let name=match &h.arrays[id]{
        Array::Obj(n,_)|Array::SharedObj(n,_)|Array::LocalObj(n,_,_)=>*n,Array::Str(_)=>"java/lang/String",Array::Boolean(_)=>"java/lang/Boolean",Array::Integer(_)=>"java/lang/Integer",Array::Short(_)=>"java/lang/Short",Array::Double(_)=>"java/lang/Double",Array::Builder(_)=>"java/lang/StringBuilder",
        Array::CompletedFuture(_)=>"java/util/concurrent/CompletableFuture",Array::TimeUnit(_)=>"java/util/concurrent/TimeUnit",Array::RuntimePermission(_)=>"java/lang/RuntimePermission",Array::Stdout|Array::Stderr=>"java/io/PrintStream",Array::Class(_)=>"java/lang/Class",Array::Local(_)=>"java/lang/ThreadLocal",
        Array::Map(_,_,_)=>"java/util/concurrent/ConcurrentHashMap",Array::Queue(_)=>"java/util/concurrent/LinkedBlockingQueue",Array::ConcurrentQueue(_)=>"java/util/concurrent/ConcurrentLinkedQueue",Array::Deque(_)=>"java/util/ArrayDeque",Array::HashMap(_)=>"java/util/HashMap",Array::LinkedMap(_,_)=>"java/util/LinkedHashMap",Array::TreeMap(_,_)=>"java/util/TreeMap",Array::Character(_)=>"java/lang/Character",Array::List(_,_)=>"java/util/ArrayList",Array::Set(_,_)=>"java/util/LinkedHashSet",Array::HashSet(_,_)=>"java/util/HashSet",
        Array::Z(_)=>"[Z",Array::B(_)=>"[B",Array::C(_)=>"[C",Array::S(_)=>"[S",Array::I(_)=>"[I",Array::J(_)=>"[J",Array::F(_)=>"[F",Array::D(_)=>"[D",Array::Strings(_)=>"[Ljava/lang/String;",Array::Refs(13,_)=>"[Ljava/lang/Object;",Array::Refs(14,_)=>"[Ljava/lang/Class;",
        Array::Exception(k,_,_) if k.contains('/')=>*k,
        Array::Exception(k,_,_)=>match *k {"FileNotFoundException"=>"java/io/FileNotFoundException","NoSuchFileException"=>"java/nio/file/NoSuchFileException","AccessDeniedException"=>"java/nio/file/AccessDeniedException","FileSystemException"=>"java/nio/file/FileSystemException","Exception"=>"java/lang/Exception","RuntimeException"=>"java/lang/RuntimeException","IllegalArgumentException"=>"java/lang/IllegalArgumentException","IllegalStateException"=>"java/lang/IllegalStateException","NullPointerException"=>"java/lang/NullPointerException","ServiceConfigurationError"=>"java/util/ServiceConfigurationError",_=>error("Object.getClass: excepción no soportada")},
        _=>error("Object.getClass: tipo no soportado"),
    };class_literal(h,name)
}
// Bajo opt-in de classpath cerrado, el índice verificó ausencia de esta clase.
fn class_for_name_absent_osgi(h:&Heap,name:Option<usize>)->Option<usize>{
    let units=string_units(h,name);
    if units.iter().copied().eq("org.osgi.framework.FrameworkUtil".encode_utf16()){raise("ClassNotFoundException","org.osgi.framework.FrameworkUtil");}
    error("Class.forName: nombre fuera del perfil verificado")
}
// Lookup cerrado: solo clases ya validadas/precompiladas o literales admitidos.
// Desconocida no implica ClassNotFoundException: abortamos explícitamente.
fn class_module(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);match h.arrays[id]{Array::Class("java/lang/Runtime")=>(),_=>error("Class.getModule: clase fuera del perfil")};if let Some(id)=h.base_module{return id;}let id=h.arrays.len();if id>=10000{error("Límite experimental de heap excedido");}h.arrays.push(Array::BaseModule);h.base_module=Some(id);id}
fn module_layer(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);if !matches!(h.arrays[id],Array::BaseModule){error("Module.getLayer: módulo fuera del perfil");}if let Some(id)=h.boot_layer{return id;}let id=h.arrays.len();if id>=10000{error("Límite experimental de heap excedido");}h.arrays.push(Array::BootLayer);h.boot_layer=Some(id);id}
fn find_jfr_module(h:&mut Heap,r:Option<usize>,name:Option<usize>)->Option<usize>{let id=array_id(h,r);if !matches!(h.arrays[id],Array::BootLayer){error("ModuleLayer no soportado");}let expected:Vec<u16>="jdk.jfr".encode_utf16().collect();if string_units(h,name)!=expected{error("ModuleLayer.findModule: nombre fuera del perfil");}if let Some(id)=h.jfr_module{return Some(id);}let id=h.arrays.len();if id>=10000{error("Límite experimental de heap excedido");}h.arrays.push(Array::JfrModule);h.jfr_module=Some(id);Some(id)}
fn class_canonical_top(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);let name=match h.arrays[id]{Array::Class(n)=>n,_=>error("Class concreto no soportado")};if name.starts_with('[')||name.contains('$')||name.len()==1{error("Class.getCanonicalName: solo clases de nivel superior");}class_get_name(h,r)}
fn class_simple_name(h:&mut Heap,r:Option<usize>)->usize{let id=array_id(h,r);let mut name=match h.arrays[id]{Array::Class(n)=>n,_=>error("Class concreto no soportado")};let original=name;if let Some(id)=h.simple_names.get(original){return *id;}let mut dims=0;while let Some(n)=name.strip_prefix('['){dims+=1;name=n;}if name.starts_with('L')&&name.ends_with(';'){name=&name[1..name.len()-1];}if name.contains('$'){error("Class.getSimpleName: clases anidadas/locales no soportadas");}let simple=match name{"Z"=>"boolean","B"=>"byte","C"=>"char","S"=>"short","I"=>"int","J"=>"long","F"=>"float","D"=>"double","V"=>"void",_=>name.rsplit('/').next().unwrap_or(name)};let mut units:Vec<u16>=simple.encode_utf16().collect();for _ in 0..dims{units.extend([91,93]);}let out=if dims==0&&original.len()==1{string_literal(h,&units)}else{new_string(h,units)};h.simple_names.insert(original,out);out}
fn classloader_load(h:&mut Heap,loader:Option<usize>,name:Option<usize>,known:&'static [(&'static str,&'static str)])->usize{
    let id=array_id(h,loader);if !matches!(h.arrays[id],Array::AppLoader){error("ClassLoader no soportado");}
    let units=string_units(h,name);
    let class=known.iter().find(|(binary,_)|binary.encode_utf16().eq(units.iter().copied())).map(|(_,internal)|*internal).unwrap_or_else(||error("ClassLoader.loadClass: clase no precompilada o desconocida"));
    class_literal(h,class)
}
fn reflect_array_empty(h:&Heap,r:Option<usize>)->bool {match r {None=>true,Some(id)=>match h.arrays.get(id){Some(Array::Strings(v))|Some(Array::Refs(_,v))|Some(Array::ProjectRefs(_,v))=>v.is_empty(),_=>panic!("se esperaba array de referencia")}}}
fn reflect_get_constructor(h:&mut Heap,class:Option<usize>,args:Option<usize>,registry:&'static [(&'static str,bool)])->usize {
    let id=array_id(h,class);let name=match h.arrays[id]{Array::Class(n)=>n,_=>panic!("se esperaba Class")};
    if !reflect_array_empty(h,args){error("Class.getConstructor: parámetros no vacíos no soportados");}
    let available=registry.iter().find(|(n,_)|*n==name).map(|(_,v)|*v).unwrap_or_else(||error("Class.getConstructor: clase no registrada para reflexión"));
    if !available{raise("NoSuchMethodException","");}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}
    let id=h.arrays.len();h.arrays.push(Array::Constructor(name));id
}
fn reflect_get_declared_constructor(h:&mut Heap,class:Option<usize>,args:Option<usize>,registry:&'static [(&'static str,bool,bool)])->usize{
    let id=array_id(h,class);let name=match h.arrays[id]{Array::Class(n)=>n,_=>panic!("se esperaba Class")};if !reflect_array_empty(h,args){error("Class.getDeclaredConstructor: parámetros no vacíos no soportados");}
    let (_,public,declared)=registry.iter().find(|(n,_,_)|*n==name).copied().unwrap_or_else(||error("Class.getDeclaredConstructor: clase no registrada para reflexión"));
    if !declared{raise("NoSuchMethodException","");}if !public{error("Class.getDeclaredConstructor: constructor no público fuera del perfil");}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Constructor(name));id
}
fn reflect_refs(h:&Heap,r:Option<usize>)->Vec<Option<usize>>{match r{None=>Vec::new(),Some(id)=>match &h.arrays[id]{Array::Strings(v)|Array::Refs(_,v)|Array::ProjectRefs(_,v)=>v.clone(),_=>error("reflexión: array no soportado")}}}
fn reflect_get_method(h:&mut Heap,class:Option<usize>,name:Option<usize>,args:Option<usize>,registry:&'static [(&'static str,&'static str,&'static str)])->usize{
    let id=array_id(h,class);let class=match h.arrays[id]{Array::Class(n)=>n,_=>panic!("se esperaba Class")};let units=string_units(h,name);let params=reflect_refs(h,args);
    let param=match params.as_slice(){[]=>"",[Some(id)]=>match h.arrays[*id]{Array::Class(n)=>n,_=>error("Class.getMethod: parámetro no Class")},_=>error("Class.getMethod: parámetros no soportados")};
    let idx=registry.iter().position(|(c,n,p)|*c==class&&*p==param&&n.encode_utf16().eq(units.iter().copied())).unwrap_or_else(||error("Class.getMethod: método no registrado"));
    if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::ReflectMethod(idx));id
}
fn reflect_method_index(h:&Heap,method:Option<usize>)->usize {let id=array_id(h,method);match h.arrays[id]{Array::ReflectMethod(n)=>n,_=>error("Method concreto no soportado")}}
fn reflect_check_count(h:&Heap,args:Option<usize>,expected:usize){if reflect_refs(h,args).len()!=expected{raise("IllegalArgumentException","");}}
fn reflect_receiver(h:&Heap,r:Option<usize>,class:&str)->usize{let id=array_id(h,r);if !matches!(&h.arrays[id],Array::Obj(n,_)|Array::SharedObj(n,_)|Array::LocalObj(n,_,_) if project_subtype(h,n,class)){raise("IllegalArgumentException","");}id}
fn reflect_argument(h:&Heap,args:Option<usize>,class:&str,interfaces:&[(&str,&str)])->Option<usize>{let v=reflect_refs(h,args)[0];if v.is_some()&&!project_instance(h,v,class,interfaces){raise("IllegalArgumentException","");}v}
fn reflect_ctor_class(h:&Heap,ctor:Option<usize>,args:Option<usize>)->&'static str {
    let id=array_id(h,ctor);let class=match h.arrays[id]{Array::Constructor(n)=>n,_=>panic!("se esperaba Constructor")};
    if !reflect_array_empty(h,args){raise("IllegalArgumentException","");}class
}
fn wrap_invocation(h:&mut Heap,p:Box<dyn std::any::Any+Send>)->! {
    if let Some(e)=p.downcast_ref::<JException>() {let cause=exception_ref(h,e);let id=new_exception(h,"InvocationTargetException");h.causes.insert(id,cause);throw_ref(h,Some(id));}
    std::panic::resume_unwind(p)
}
// Se preservan los null; imprimir stack trace real todavía no está implementado.
fn print_stack_trace_guard(h:&Heap,e:Option<usize>,stream:Option<usize>){
    let id=array_id(h,e);if !matches!(h.arrays[id],Array::Exception(_,_,_)){panic!("se esperaba Throwable");}
    array_id(h,stream);error("Throwable.printStackTrace: stack traces no implementados");
}
fn invocation_cause(h:&Heap,r:Option<usize>)->Option<usize>{
    let id=array_id(h,r);if !matches!(h.arrays[id],Array::Exception(_,_,_)){error("Throwable.getCause: tipo no soportado");}h.causes.get(&id).copied()
}
fn service_error_message(h:&Heap,r:Option<usize>)->Option<usize>{
    let id=array_id(h,r);match h.arrays[id]{Array::Exception("ServiceConfigurationError",_,Some(msg))=>Some(msg),_=>error("ServiceConfigurationError.getMessage: caso no soportado")}
}
fn service_fail(h:&mut Heap,service:&str,description:&str,cause:Option<usize>)->! {
    let msg=format!("{}: {}",service.replace('/',"."),description);let msg_id=new_string(h,msg.encode_utf16().collect());
    let id=new_exception(h,"ServiceConfigurationError");init_exception(h,Some(id),"ServiceConfigurationError",Some(msg_id));if let Some(c)=cause{h.causes.insert(id,c);}throw_ref(h,Some(id))
}
// Recurso concreto usado por SLF4J; catálogo del bundle y plataforma Java 25.
// Si existe hay que modelar URL: se rechaza, jamás se devuelve vacío por defecto.
fn classloader_resources(h:&mut Heap,loader:Option<usize>,name:Option<usize>,binder_present:bool,provider_absent:bool)->usize {
    let lid=array_id(h,loader);if !matches!(h.arrays[lid],Array::AppLoader){error("ClassLoader.getResources: loader no soportado");}
    let units=string_units(h,name);if "org/slf4j/impl/StaticLoggerBinder.class".encode_utf16().eq(units.iter().copied()){if binder_present{error("ClassLoader.getResources: recursos URL presentes no soportados");}}
    else if "META-INF/log4j-provider.properties".encode_utf16().eq(units.iter().copied()){if !provider_absent{error("ClassLoader.getResources: ausencia del proveedor no verificada o falta MC_AOT_CLOSED_CLASSPATH=1");}}
    else{error("ClassLoader.getResources: recurso no soportado");}
    if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::EmptyEnumeration);id
}
fn empty_enumeration_has_next(h:&Heap,r:Option<usize>)->bool{let id=array_id(h,r);if !matches!(h.arrays[id],Array::EmptyEnumeration){error("Enumeration concreta no soportada");}false}
fn empty_enumeration_next(h:&Heap,r:Option<usize>)->!{empty_enumeration_has_next(h,r);raise("NoSuchElementException","")}
// Catálogo de recursos del bundle; proveedores solo si su constructor fue registrado.
fn service_load(h:&mut Heap,service:Option<usize>,loader:Option<usize>,catalog:&'static [(&'static str,&'static [&'static str])])->usize {
    let sid=array_id(h,service);let name=match h.arrays[sid]{Array::Class(n)=>n,_=>panic!("se esperaba Class")};
    let lid=loader.unwrap_or_else(||error("ServiceLoader: loader null no soportado"));
    if !matches!(h.arrays.get(lid),Some(Array::AppLoader)){error("ServiceLoader: loader no soportado");}
    let providers=catalog.iter().find(|(n,_)|*n==name).map(|(_,p)|*p).unwrap_or_else(||error("ServiceLoader: servicio sin catálogo soportado"));
    if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Service(name,providers,0,Vec::new()));id
}
fn service_iterator(h:&mut Heap,service:Option<usize>)->usize {
    let id=array_id(h,service);if !matches!(h.arrays[id],Array::Service(_,_,_,_)){error("ServiceLoader: referencia no soportada");}
    if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let n=h.arrays.len();h.arrays.push(Array::ServiceIter(id,0));n
}
fn iterable_iterator(h:&mut Heap,r:Option<usize>)->usize {
    let id=array_id(h,r);
    if matches!(h.arrays[id],Array::Service(_,_,_,_)){service_iterator(h,r)}else{collection_iterator(h,r)}
}
fn service_position(h:&Heap,iter:Option<usize>)->(usize,usize,usize){
    let id=array_id(h,iter);match h.arrays[id]{Array::ServiceIter(owner,cursor)=>(id,owner,cursor),_=>error("Iterator que no es de ServiceLoader no soportado")}
}
fn service_has_next(h:&Heap,iter:Option<usize>,registry:&[(&str,bool)],interfaces:&[(&str,&str)])->bool {
    let (_,owner,cursor)=service_position(h,iter);
    let (service,providers,next,cache)=match &h.arrays[owner]{Array::Service(s,p,n,c)=>(*s,*p,*n,c),_=>panic!("ServiceLoader inválido")};
    // Java almacena un error de configuración pendiente y hasNext devuelve true;
    // la excepción se lanza al invocar next, no aquí.
    cursor<cache.len() || next<providers.len()
}
fn service_next(h:&mut Heap,iter:Option<usize>,registry:&[(&str,bool)],interfaces:&[(&str,&str)],construct:fn(&mut Heap,Option<usize>,Option<usize>)->Option<usize>)->Option<usize> {
    if !service_has_next(h,iter,registry,interfaces){raise("NoSuchElementException","");}
    let (id,owner,cursor)=service_position(h,iter);
    let cached=match &h.arrays[owner]{Array::Service(_,_,_,v)=>v.get(cursor).copied(),_=>unreachable!()};
    let result=if let Some(value)=cached{value}else{
        let name=match &mut h.arrays[owner]{Array::Service(_,providers,next,_)=>{let name=providers[*next];*next+=1;name},_=>unreachable!()};
        if name.starts_with('!'){error("ServiceLoader: recurso inválido o no ASCII no soportado");}
        let service=match &h.arrays[owner]{Array::Service(s,_,_,_)=>*s,_=>unreachable!()};
        let constructor=registry.iter().find(|(c,_)|*c==name).map(|(_,v)|*v).unwrap_or_else(||error(&format!("ServiceLoader: proveedor no registrado para reflexión: {name} (servicio {service})")));
        if !interfaces.iter().any(|(c,i)|*c==name && *i==service) {service_fail(h,service,&format!("{} not a subtype",name.replace('/',".")),None);}
        if !constructor {let cause=new_exception(h,"NoSuchMethodException");service_fail(h,service,&format!("{} Unable to get public no-arg constructor",name.replace('/',".")),Some(cause));}
        if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let ctor=h.arrays.len();h.arrays.push(Array::Constructor(name));
        let call=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||{let _opaque=call_guard("<jdk-callback>");construct(h,Some(ctor),None)}));
        let value=match call {Ok(Some(v))=>v,Ok(None)=>panic!("constructor sin objeto"),Err(p)=>{
            if let Some(e)=p.downcast_ref::<JException>(){let cause=if e.kind=="InvocationTargetException" {e.id.and_then(|id|h.causes.get(&id).copied())}else{Some(exception_ref(h,e))};
                service_fail(h,service,&format!("Provider {} could not be instantiated",name.replace('/',".")),cause);}
            std::panic::resume_unwind(p)
        }};
        if let Array::Service(_,_,_,cache)=&mut h.arrays[owner]{cache.push(value);}value
    };
    if let Array::ServiceIter(_,position)=&mut h.arrays[id]{*position+=1;}Some(result)
}
fn monitor_holds(h:&Heap,r:Option<usize>)->bool{let id=array_id(h,r);match &h.arrays[id]{Array::SharedObj(_,o)=>o.monitor.holds().unwrap_or_else(|e|error(e)),_=>h.monitors.get(&id).copied().unwrap_or(0)>0}}
fn monitor_enter(h:&mut Heap,r:Option<usize>){let id=array_id(h,r);match &h.arrays[id]{Array::SharedObj(_,o)=>o.monitor.enter().unwrap_or_else(|e|error(e)),_=>{let count=h.monitors.entry(id).or_insert(0);*count=count.checked_add(1).unwrap_or_else(||error("límite de monitor excedido"));}}}
fn monitor_exit(h:&mut Heap,r:Option<usize>){let id=array_id(h,r);match &h.arrays[id]{Array::SharedObj(_,o)=>match o.monitor.exit(){Ok(())=>(),Err("monitor no adquirido")=>raise("IllegalMonitorStateException",""),Err(e)=>error(e)},_=>match h.monitors.get_mut(&id){Some(count) if *count>0=>*count-=1,_=>raise("IllegalMonitorStateException","")}}}

// ArrayList por referencias, sin igualdad arbitraria; iterator fail-fast acotado.
fn collection_iterator(h:&mut Heap,r:Option<usize>)->usize {
    let owner=array_id(h,r);if matches!(h.arrays[owner],Array::EmptyList|Array::EmptySet){return empty_iterator(h);}let value=match &h.arrays[owner]{Array::PropertiesEntries(map)=>{properties_empty_iter(h,*map);Array::PropertiesEmptyIter(*map)},Array::EnumSet(v)=>Array::EnumSetIter(v.clone(),0),Array::TreeEntries(map)=>match h.arrays[*map]{Array::TreeMap(ref values,version)=>Array::TreeIter(*map,values.iter().map(|(k,_)|*k).collect(),0,version,true),_=>unreachable!()},Array::MapValues(map)=>match h.arrays[*map]{Array::TreeMap(ref values,version)=>Array::TreeIter(*map,values.iter().map(|(k,_)|*k).collect(),0,version,false),Array::LinkedMap(ref values,version)=>Array::LinkedIter(*map,values.iter().map(|(k,_)|*k).collect(),0,version),_=>error("iterator de Map.values no soportado")},Array::List(_,v)=>Array::ListIter(owner,0,*v),Array::ImmutableList(_)=>Array::ArraysListIter(owner,0),Array::ArraysList(_)=>Array::ArraysListIter(owner,0),Array::Set(v,n)|Array::HashSet(v,n)=>{if matches!(h.arrays[owner],Array::HashSet(_,_))&&v.len()>1{error("HashSet.iterator: orden no verificado");}if h.elements.checked_add(v.len()).map_or(true,|x|x>1_000_000){error("Límite experimental de heap excedido");}Array::SetIter(owner,v.clone(),0,*n)},_=>error("iterator de colección no soportada")};
    if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let added=match &value{Array::SetIter(_,v,_,_)|Array::LinkedIter(_,v,_,_)=>v.len(),Array::TreeIter(_,v,_,_,_)|Array::EnumSetIter(v,_)=>v.len(),_=>0};if h.elements.checked_add(added).map_or(true,|x|x>1_000_000){error("Límite experimental de heap excedido");}h.elements+=added;let id=h.arrays.len();h.arrays.push(value);id
}
fn iterator_has_next(h:&Heap,r:Option<usize>,registry:&[(&str,bool)],interfaces:&[(&str,&str)])->bool {
    let id=array_id(h,r);match h.arrays[id] {
        Array::PropertiesEmptyIter(map)=>{properties_empty_iter(h,map);false},
        Array::EnumSetIter(ref values,cursor)=>cursor<values.len(),
        Array::LinkedIter(_,ref keys,cursor,_)=>cursor<keys.len(),
        Array::TreeIter(_,ref keys,cursor,_,_)=>cursor<keys.len(),
        Array::EmptyIterator=>false,
        Array::ArraysListIter(owner,cursor)=>cursor < collection_size(h,Some(owner)) as usize,
        Array::ListIter(owner,cursor,_)=>match &h.arrays[owner]{Array::List(v,_)=>cursor!=v.len(),_=>panic!("List inválida")},
        Array::SetIter(_,ref items,cursor,_)=>cursor<items.len(),
        Array::ServiceIter(_,_)=>service_has_next(h,r,registry,interfaces),_=>error("Iterator concreto no soportado"),
    }
}
fn iterator_next(h:&mut Heap,r:Option<usize>,registry:&[(&str,bool)],interfaces:&[(&str,&str)],construct:fn(&mut Heap,Option<usize>,Option<usize>)->Option<usize>)->Option<usize> {
    let id=array_id(h,r);match h.arrays[id] {
        Array::PropertiesEmptyIter(map)=>{properties_empty_iter(h,map);raise("NoSuchElementException","")},
        Array::EnumSetIter(ref values,cursor)=>{let value=*values.get(cursor).unwrap_or_else(||raise("NoSuchElementException",""));if let Array::EnumSetIter(_,pos)=&mut h.arrays[id]{*pos+=1;}Some(value)},
        Array::LinkedIter(map,ref keys,cursor,version)=>{let actual=match &h.arrays[map]{Array::LinkedMap(_,v)=>*v,_=>unreachable!()};if actual!=version{raise("ConcurrentModificationException","");}let key=*keys.get(cursor).unwrap_or_else(||raise("NoSuchElementException",""));let i=hashmap_pos(h,map,key).unwrap_or_else(||error("LinkedHashMap iterador inconsistente"));let value=match &h.arrays[map]{Array::LinkedMap(v,_)=>v[i].1,_=>unreachable!()};if let Array::LinkedIter(_,_,pos,_)=&mut h.arrays[id]{*pos+=1;}value},
        Array::TreeIter(map,ref keys,cursor,version,entry)=>{let key=*keys.get(cursor).unwrap_or_else(||raise("NoSuchElementException",""));let actual=match &h.arrays[map]{Array::TreeMap(_,actual)=>*actual,_=>unreachable!()};if actual!=version{raise("ConcurrentModificationException","");}let index=tree_search(h,map,Some(key)).unwrap_or_else(|_|error("TreeMap iterador inconsistente"));let val=match &h.arrays[map]{Array::TreeMap(v,_)=>v[index].1,_=>unreachable!()};if let Array::TreeIter(_,_,pos,_,_)=&mut h.arrays[id]{*pos+=1;}if entry{if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let out=h.arrays.len();h.arrays.push(Array::TreeEntry(map,key,actual));Some(out)}else{val}},
        Array::EmptyIterator=>raise("NoSuchElementException",""),
        Array::ArraysListIter(owner,cursor)=>{if cursor>=collection_size(h,Some(owner)) as usize{raise("NoSuchElementException","");}let v=list_get(h,Some(owner),cursor as i32);if let Array::ArraysListIter(_,pos)=&mut h.arrays[id]{*pos+=1;}v},
        Array::ListIter(owner,cursor,expected)=>{
            let value=match &h.arrays[owner]{Array::List(v,version)=>{if *version!=expected{raise("ConcurrentModificationException","");}if cursor>=v.len(){raise("NoSuchElementException","");}v[cursor]},_=>panic!("List inválida")};
            if let Array::ListIter(_,position,_)=&mut h.arrays[id]{*position+=1;}value
        },
        Array::SetIter(owner,ref items,cursor,expected)=>{
            let actual=match &h.arrays[owner]{Array::Set(_,v)|Array::HashSet(_,v)=>*v,_=>panic!("Set inválido")};if actual!=expected{raise("ConcurrentModificationException","");}if cursor>=items.len(){raise("NoSuchElementException","");}let value=items[cursor];
            if let Array::SetIter(_,_,pos,_)=&mut h.arrays[id]{*pos+=1;}value
        },
        Array::ServiceIter(_,_)=>service_next(h,r,registry,interfaces,construct),_=>error("Iterator concreto no soportado"),
    }
}
fn string_value_of_object(h:&mut Heap,value:Option<usize>)->usize{match value{None=>string_literal(h,&[110,117,108,108]),Some(id)=>match h.arrays.get(id){Some(Array::Str(_))=>id,Some(Array::Uri(s))=>*s,_=>error("String.valueOf(Object): solo String/null soportado salvo URI CommonLinks")}}}
fn concat_ref(h:&Heap,out:&mut Vec<u16>,value:Option<usize>){match value{None=>out.extend("null".encode_utf16()),Some(id)=>match h.arrays.get(id){Some(Array::Str(v))=>out.extend_from_slice(v),_=>error("invokedynamic concat: Object distinto de String no soportado")}}}
fn arrays_as_list(h:&mut Heap,r:Option<usize>)->usize{
    let array=array_id(h,r);if !matches!(h.arrays[array],Array::Strings(_)|Array::Refs(_,_)|Array::ProjectRefs(_,_)){error("Arrays.asList: solo arrays de referencia");}
    if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::ArraysList(array));id
}
fn list_to_string(h:&mut Heap,r:Option<usize>)->usize {
    let id=list_id(h,r);if matches!(h.arrays[id],Array::EmptyList){return string_literal(h,&[91,93]);}let values=match &h.arrays[id]{Array::List(v,_)=>v.clone(),Array::ArraysList(a)=>match &h.arrays[*a]{Array::Strings(v)|Array::Refs(_,v)|Array::ProjectRefs(_,v)=>v.clone(),_=>unreachable!()},_=>unreachable!()};
    let mut out=vec![b'[' as u16];for (i,v) in values.iter().enumerate(){if i>0{out.extend(", ".encode_utf16());}match v{None=>out.extend("null".encode_utf16()),Some(x)=>match &h.arrays[*x]{Array::Str(v)=>out.extend(v),_=>error("List.toString: solo String/null soportado")}}}out.push(b']' as u16);new_string(h,out)
}
fn list_id(h:&Heap,r:Option<usize>)->usize{let id=array_id(h,r);if !matches!(h.arrays[id],Array::List(_,_)|Array::ArraysList(_)|Array::EmptyList|Array::ImmutableList(_)){error("List concreta no soportada");}id}
fn list_index(i:i32,n:usize)->usize{if i<0||i as usize>=n{raise("IndexOutOfBoundsException","");}i as usize}
fn list_get(h:&Heap,r:Option<usize>,i:i32)->Option<usize>{let id=list_id(h,r);match &h.arrays[id]{Array::List(v,_)|Array::ImmutableList(v)=>v[list_index(i,v.len())],Array::EmptyList=>{list_index(i,0);unreachable!()},Array::ArraysList(a)=>match array_load(h,Some(*a),i,0x32){V::R(v)=>v,_=>unreachable!()},_=>unreachable!()}}
fn list_set(h:&mut Heap,r:Option<usize>,i:i32,val:Option<usize>)->Option<usize>{let id=list_id(h,r);if matches!(h.arrays[id],Array::EmptyList|Array::ImmutableList(_)){raise("UnsupportedOperationException","");}if let Array::ArraysList(a)=h.arrays[id]{let prev=list_get(h,r,i);array_store(h,Some(a),i,V::R(val),0x53);return prev;}match &mut h.arrays[id]{Array::List(v,_)=>{let ix=list_index(i,v.len());let prev=v[ix];v[ix]=val;prev},_=>unreachable!()}}
fn list_remove(h:&mut Heap,r:Option<usize>,i:i32)->Option<usize>{let id=list_id(h,r);if matches!(h.arrays[id],Array::ArraysList(_)|Array::EmptyList|Array::ImmutableList(_)){raise("UnsupportedOperationException","");}match &mut h.arrays[id]{Array::List(v,version)=>{let ix=list_index(i,v.len());*version=version.wrapping_add(1);v.remove(ix)},_=>unreachable!()}}
// Only direct, final subclasses with no overrides of these base operations are admitted.
fn spliterator_init(h:&mut Heap,r:Option<usize>,size:i64,flags:i32){let id=array_id(h,r);if !matches!(h.arrays[id],Array::Obj(_,_)|Array::SharedObj(_,_)|Array::LocalObj(_,_,_)){error("AbstractSpliterator: receptor no soportado");}let flags=if flags&64!=0 {flags|16384} else {flags};h.spliterators.insert(id,(size,flags));}
fn spliterator_state(h:&Heap,r:Option<usize>)->(i64,i32){let id=array_id(h,r);*h.spliterators.get(&id).unwrap_or_else(||error("Spliterator: receptor fuera del perfil"))}
fn stream_support(h:&mut Heap,r:Option<usize>,parallel:i32)->usize{let id=array_id(h,r);let (_,flags)=spliterator_state(h,Some(id));if flags&4!=0{raise("IllegalStateException","");}if parallel!=0{error("StreamSupport: stream paralelo no soportado");}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let out=h.arrays.len();h.arrays.push(Array::LazyStream(id,false,None,false));out}
fn comparator_comparing(h:&mut Heap,extractor:Option<usize>)->usize {let f=array_id(h,extractor);if !matches!(h.arrays[f],Array::Lambda(_,"java/util/function/Function",_)|Array::IdentityFunction){error("Comparator.comparing: Function fuera del perfil");}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let id=h.arrays.len();h.arrays.push(Array::Comparing(f));id}
fn comparator_compare(h:&mut Heap,r:Option<usize>,a:Option<usize>,b:Option<usize>,apply:fn(&mut Heap,Option<usize>,Option<usize>)->Option<usize>)->i32 {let id=array_id(h,r);let f=match h.arrays[id]{Array::Comparing(f)=>f,_=>error("Comparator.compare: comparador fuera del perfil")};let x={let _opaque=call_guard("<jdk-callback>");apply(h,Some(f),a)};if let Some(id)=x{if !matches!(h.arrays[id],Array::Integer(_)){error("Comparator.compare: claves distintas de Integer no soportadas");}}let y={let _opaque=call_guard("<jdk-callback>");apply(h,Some(f),b)};let xi=array_id(h,x);let yi=array_id(h,y);match (&h.arrays[xi],&h.arrays[yi]){(Array::Integer(x),Array::Integer(y))=>match x.cmp(y){std::cmp::Ordering::Less=>-1,std::cmp::Ordering::Equal=>0,std::cmp::Ordering::Greater=>1},_=>error("Comparator.compare: claves distintas de Integer no soportadas")}}
// ArrayList's stream is lazy and observes the list at the terminal operation.
// Consumption of this source is intentionally rejected until traversal semantics exist.
fn collection_stream(h:&mut Heap,r:Option<usize>)->usize {let id=array_id(h,r);if !matches!(h.arrays[id],Array::List(_,_)|Array::Set(_,_)|Array::HashSet(_,_)|Array::KeySet(_,_)){error("Collection.stream: fuente fuera del perfil");}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let out=h.arrays.len();h.arrays.push(Array::LazyStream(id,false,None,false));out}
fn stream_is_parallel(h:&Heap,r:Option<usize>)->bool{let id=array_id(h,r);if !matches!(h.arrays[id],Array::LazyStream(_,_,_,_)|Array::SortedStream(_,_,_)|Array::MappedStream(_,_,_)){error("Stream: receptor fuera del perfil");}false}
fn stream_close(h:&mut Heap,r:Option<usize>){let id=array_id(h,r);match &mut h.arrays[id]{Array::LazyStream(_,linked,parent,taken)=>{*linked=true;if parent.is_none(){*taken=true;}},Array::SortedStream(_,linked,_)|Array::MappedStream(_,linked,_)=>*linked=true,_=>error("Stream: receptor fuera del perfil")}}
// forEach de la ruta Log4j; el Spliterator debe ser el bytecode oficial verificado.
fn stream_for_each(h:&mut Heap,r:Option<usize>,action:Option<usize>,advance:fn(&mut Heap,Option<usize>,Option<usize>)->i32){
    let stage=array_id(h,r);let is_head=match h.arrays[stage]{Array::LazyStream(_,_,p,_)=>p.is_none(),Array::SortedStream(_,_,_)|Array::MappedStream(_,_,_)=>false,_=>error("Stream: receptor fuera del perfil")};
    // ReferencePipeline.Head obtiene la fuente antes de comprobar consumer null;
    // las etapas intermedias lo comprueban antes de marcarse consumidas.
    if !is_head && action.is_none(){raise("NullPointerException","");}
    match h.arrays[stage]{Array::LazyStream(_,true,_,_)|Array::SortedStream(_,true,_)|Array::MappedStream(_,true,_)=>raise("IllegalStateException","stream has already been operated upon or closed"),Array::LazyStream(_,false,_,_)|Array::SortedStream(_,false,_)|Array::MappedStream(_,false,_)=>{},_=>unreachable!()};
    match &mut h.arrays[stage]{Array::LazyStream(_,linked,_,_)|Array::SortedStream(_,linked,_)|Array::MappedStream(_,linked,_)=>*linked=true,_=>unreachable!()}
    let mut cur=stage;let mut predicates=Vec::new();let source=loop{match h.arrays[cur]{Array::LazyStream(source,_,None,taken)=>{if taken{raise("IllegalStateException","source already consumed or closed");}break source},Array::LazyStream(parent,_,Some(pred),_)=>{predicates.push(pred);cur=parent;},Array::SortedStream(_,_,_)=>error("Stream.sorted: consumo ordenado no implementado"),Array::MappedStream(_,_,_)=>error("Stream.map: consumo transformado no implementado"),_=>error("Stream: cadena inválida")}};
    if let Array::LazyStream(_,_,_,taken)=&mut h.arrays[cur]{*taken=true;}
    let consumer=array_id(h,action);
    let class=match h.arrays.get(source){Some(Array::Obj(class,_))|Some(Array::SharedObj(class,_))|Some(Array::LocalObj(class,_,_))=>*class,_=>error("Stream.forEach: fuente fuera del perfil")};
    if class!="org/apache/logging/log4j/util/ServiceLoaderUtil$ServiceLoaderSpliterator"{error("Stream.forEach: solo Spliterator oficial de Log4j soportado");}
    predicates.reverse();let downstream=if predicates.is_empty(){consumer}else{if h.arrays.len()>=10000||h.elements.saturating_add(predicates.len())>1_000_000{error("Límite experimental de heap excedido");}h.elements+=predicates.len();let id=h.arrays.len();h.arrays.push(Array::StreamSink(predicates,consumer));id};
    for _ in 0..1_000_000 {if {let _opaque=call_guard("<jdk-callback>");advance(h,Some(source),Some(downstream))}&1==0{return;}}
    error("Stream.forEach: límite de avance excedido");
}
fn stream_filter(h:&mut Heap,r:Option<usize>,predicate:Option<usize>)->usize{
    let id=array_id(h,r);let pred=array_id(h,predicate);if !matches!(h.arrays[pred],Array::Lambda(_,"java/util/function/Predicate",_)){error("Stream.filter: Predicate fuera del perfil");}
    match h.arrays[id]{Array::LazyStream(_,false,_,_)|Array::SortedStream(_,false,_)|Array::MappedStream(_,false,_)=>{},Array::LazyStream(_,true,_,_)|Array::SortedStream(_,true,_)|Array::MappedStream(_,true,_)=>raise("IllegalStateException","stream has already been operated upon or closed"),_=>error("Stream: receptor fuera del perfil")};
    if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}match &mut h.arrays[id]{Array::LazyStream(_,linked,_,_)|Array::SortedStream(_,linked,_)|Array::MappedStream(_,linked,_)=>*linked=true,_=>unreachable!()}let out=h.arrays.len();h.arrays.push(Array::LazyStream(id,false,Some(pred),false));out
}
fn stream_collect_joining(h:&mut Heap,r:Option<usize>,collector:Option<usize>)->usize {let id=array_id(h,r);let collector=array_id(h,collector);let (delim,prefix,suffix)=match h.arrays[collector]{Array::JoinCollector(d,p,s)=>(d,p,s),_=>error("Stream.collect: solo Collectors.joining soportado")};let source=match h.arrays[id]{Array::LazyStream(src,false,None,false)=>src,Array::LazyStream(_,true,_,_)|Array::SortedStream(_,true,_)|Array::MappedStream(_,true,_)=>raise("IllegalStateException","stream has already been operated upon or closed"),_=>error("Stream.collect: solo ArrayList directo sin etapas")};if !matches!(h.arrays[source],Array::List(_,_)){error("Stream.collect: solo ArrayList directo sin etapas");}if let Array::LazyStream(_,linked,_,taken)=&mut h.arrays[id]{*linked=true;*taken=true;}let prefix=prefix.unwrap_or_else(||raise("NullPointerException","The prefix must not be null"));let delim=delim.unwrap_or_else(||raise("NullPointerException","The delimiter must not be null"));let suffix=suffix.unwrap_or_else(||raise("NullPointerException","The suffix must not be null"));let items=match &h.arrays[source]{Array::List(v,_)=>v,_=>unreachable!()};let mut out=Vec::new();let mut append=|part:&[u16]|{if out.len().checked_add(part.len()).map_or(true,|n|n>1_000_000){error("Stream.collect: límite de cadena excedido");}out.extend_from_slice(part);};append(string_units(h,Some(prefix)));for (i,value) in items.iter().enumerate(){if i>0{append(string_units(h,Some(delim)));}match value{None=>append(&[110,117,108,108]),Some(v)=>match &h.arrays[*v]{Array::Str(s)=>append(s),_=>error("Stream.collect: elemento distinto de String/null")}}}append(string_units(h,Some(suffix)));new_string(h,out)}
fn stream_map(h:&mut Heap,r:Option<usize>,fun:Option<usize>)->usize {let id=array_id(h,r);if matches!(h.arrays[id],Array::StackWalkStream(_,_,_,_,_)|Array::StackStage(_,_,_,_)){return stack_stage_new(h,r,fun,0);}let f=array_id(h,fun);if !matches!(h.arrays[f],Array::Lambda(_,"java/util/function/Function",_)|Array::IdentityFunction){error("Stream.map: Function fuera del perfil");}match &mut h.arrays[id]{Array::LazyStream(_,linked,_,_)|Array::SortedStream(_,linked,_)|Array::MappedStream(_,linked,_)=>{if *linked{raise("IllegalStateException","stream has already been operated upon or closed");}*linked=true;},_=>error("Stream.map: fuente fuera del perfil")};if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let out=h.arrays.len();h.arrays.push(Array::MappedStream(id,false,f));out}
// Sequential max for a direct ArrayList source and the Integer-key comparator only.
fn stream_max_list(h:&mut Heap,r:Option<usize>,cmp:Option<usize>,apply:fn(&mut Heap,Option<usize>,Option<usize>)->Option<usize>)->usize {let id=array_id(h,r);let cmpid=array_id(h,cmp);if !matches!(h.arrays[cmpid],Array::Comparing(_)){error("Stream.max: comparador fuera del perfil");}let source=match h.arrays[id]{Array::LazyStream(source,false,None,false)=>source,Array::LazyStream(_,true,_,_)|Array::SortedStream(_,true,_)|Array::MappedStream(_,true,_)=>raise("IllegalStateException","stream has already been operated upon or closed"),_=>error("Stream.max: solo fuente ArrayList directa")};let (length,version)=match &h.arrays[source]{Array::List(values,version)=>(values.len(),*version),_=>error("Stream.max: solo fuente ArrayList directa")};if let Array::LazyStream(_,linked,_,taken)=&mut h.arrays[id]{*linked=true;*taken=true;}let mut best=None;for i in 0..length{let value=match &h.arrays[source]{Array::List(values,v) if *v==version=>values[i],_=>error("Stream.max: modificación estructural durante recorrido no soportada")};if i==0{best=value;}else{let c=comparator_compare(h,Some(cmpid),best,value,apply);if let Array::List(_,v)=h.arrays[source]{if v!=version{error("Stream.max: modificación estructural durante recorrido no soportada");}}if c<0{best=value;}}}if length!=0&&best.is_none(){raise("NullPointerException","");}optional_new(h,best)}
// Java links the previous stage before checking the comparator for null.
fn stream_sorted(h:&mut Heap,r:Option<usize>,comparator:Option<usize>)->usize {let id=array_id(h,r);match &mut h.arrays[id]{Array::LazyStream(_,linked,_,_)|Array::SortedStream(_,linked,_)|Array::MappedStream(_,linked,_)=>{if *linked{raise("IllegalStateException","stream has already been operated upon or closed");}*linked=true;},_=>error("Stream.sorted: fuente fuera del perfil")};let cmp=array_id(h,comparator);if !matches!(h.arrays[cmp],Array::Comparing(_)){error("Stream.sorted: comparador fuera del perfil");}if h.arrays.len()>=10000{error("Límite experimental de heap excedido");}let out=h.arrays.len();h.arrays.push(Array::SortedStream(id,false,cmp));out}
fn set_pos(h:&Heap,id:usize,val:Option<usize>)->Option<usize>{
    if matches!(h.arrays[id],Array::EmptySet){return None;}
    let keyset=matches!(h.arrays[id],Array::KeySet(_,_));if keyset&&val.is_none(){raise("NullPointerException","");}
    let hashset=matches!(h.arrays[id],Array::HashSet(_,_)|Array::KeySet(_,_));
    if let Some(v)=val{match h.arrays.get(v){Some(Array::Str(_))=>{},Some(Array::Class(_)) if hashset=>{},_=>if keyset{error("KeySetView: solo claves String/Class soportadas")}else if hashset{error("HashSet: solo String/Class/null soportado")}else{error("LinkedHashSet: solo String/null soportado")}}}
    let items=match &h.arrays[id]{Array::Set(v,_)|Array::HashSet(v,_)|Array::KeySet(v,_)=>v,_=>error("Set concreto no soportado")};
    items.iter().position(|x|match (*x,val){(None,None)=>true,(Some(a),Some(b))=>match (&h.arrays[a],&h.arrays[b]){(Array::Str(x),Array::Str(y))=>x==y,(Array::Class(_),Array::Class(_))=>a==b,_=>false},_=>false})
}
fn set_contains(h:&Heap,r:Option<usize>,val:Option<usize>)->bool{let id=array_id(h,r);if let Array::IdentitySet(map)=h.arrays[id]{return map_contains(h,Some(map),val);}set_pos(h,id,val).is_some()}
fn set_remove(h:&mut Heap,r:Option<usize>,val:Option<usize>)->bool{let id=array_id(h,r);if let Array::IdentitySet(map)=h.arrays[id]{return map_remove(h,Some(map),val).is_some();}let pos=set_pos(h,id,val);if let Some(i)=pos{if let Array::Set(v,n)|Array::HashSet(v,n)|Array::KeySet(v,n)=&mut h.arrays[id]{v.remove(i);*n=n.wrapping_add(1);}true}else{false}}
fn collection_add(h:&mut Heap,r:Option<usize>,val:Option<usize>)->bool{let id=array_id(h,r);if let Array::IdentitySet(map)=h.arrays[id]{let value=boolean_value_of(h,true);return map_put(h,Some(map),val,Some(value),false).is_none();}if matches!(h.arrays[id],Array::ArraysList(_)|Array::EmptyList|Array::EmptySet|Array::ImmutableList(_)){raise("UnsupportedOperationException","");}if matches!(h.arrays[id],Array::Queue(_)|Array::ConcurrentQueue(_)|Array::Deque(_)){queue_offer(h,r,val);return true;}
    if matches!(h.arrays[id],Array::Set(_,_)|Array::HashSet(_,_)|Array::KeySet(_,_)) && set_pos(h,id,val).is_some(){return false;}
    if !matches!(h.arrays[id],Array::List(_,_)|Array::Set(_,_)|Array::HashSet(_,_)|Array::KeySet(_,_)){error("Collection concreta no soportada");}if h.elements>=1_000_000{error("Límite experimental de heap excedido");}h.elements+=1;
    match &mut h.arrays[id]{Array::List(v,version)|Array::Set(v,version)|Array::HashSet(v,version)|Array::KeySet(v,version)=>{*version=version.wrapping_add(1);v.push(val)},_=>unreachable!()}true
}
fn collection_size(h:&Heap,r:Option<usize>)->i32{let id=array_id(h,r);match &h.arrays[id]{Array::List(v,_)|Array::Set(v,_)|Array::HashSet(v,_)|Array::KeySet(v,_)|Array::ImmutableList(v)=>v.len() as i32,Array::EmptyList|Array::EmptySet=>0,Array::IdentitySet(map)=>map_size(h,Some(*map)),Array::EnumSet(v)=>v.len() as i32,Array::TreeEntries(map)=>map_size(h,Some(*map)),Array::PropertiesEntries(map)=>match &h.arrays[*map]{Array::Properties(v)=>v.len() as i32,_=>unreachable!()},Array::MapValues(map)=>map_size(h,Some(*map)),Array::ArraysList(a)=>array_len(h,Some(*a)),Array::Queue(v)|Array::ConcurrentQueue(v)|Array::Deque(v)=>v.len() as i32,_=>error("Collection concreta no soportada")}}
fn collection_clear(h:&mut Heap,r:Option<usize>){let id=array_id(h,r);if let Array::IdentitySet(map)=h.arrays[id]{map_clear(h,Some(map));return;}if matches!(h.arrays[id],Array::EmptyList|Array::EmptySet){return;}if matches!(h.arrays[id],Array::ImmutableList(_)){raise("UnsupportedOperationException","");}if let Array::TreeEntries(map)|Array::MapValues(map)=h.arrays[id]{map_clear(h,Some(map));return;}if let Array::ArraysList(a)=h.arrays[id]{if array_len(h,Some(a))>0{raise("UnsupportedOperationException","");}return;}match &mut h.arrays[id]{Array::List(v,version)|Array::Set(v,version)|Array::HashSet(v,version)|Array::KeySet(v,version)=>{*version=version.wrapping_add(1);v.clear()},Array::Queue(v)|Array::ConcurrentQueue(v)|Array::Deque(v)=>v.clear(),_=>error("Collection concreta no soportada")}}
