# default.nix

{ stdenv, fetchurl, autoPatchelfHook, gcc, glibc, lib, libgcc, ... }:

let
  version = "0.3.15";
  owner = "scottidler";
  repo = "rmrf";
  suffix = "linux";
  tarball = fetchurl {
    url = "https://github.com/${owner}/${repo}/releases/download/v${version}/rmrf-v${version}-${suffix}.tar.gz";
    sha256 = "082wk31b2ybs63rxib7ym54jly4ywwiyiz7shnxda18hl0ijsrxd";
  };
in stdenv.mkDerivation rec {
  pname = "rmrf";
  inherit version;

  src = tarball;

  nativeBuildInputs = [ autoPatchelfHook ];
  buildInputs = [ gcc glibc libgcc ];

  dontBuild = true;

  unpackPhase = ''
    mkdir -p $out/bin
    tar -xzf $src -C $out/bin --strip-components=0
  '';

  meta = with lib; {
    description = "tool for staging rmrf-ing or bkup-ing files";
    homepage = "https://github.com/${owner}/${repo}";
    license = licenses.mit;
    platforms = platforms.linux ++ platforms.darwin;
    maintainers = with maintainers; [ maintainers.scottidler ];
  };
}
