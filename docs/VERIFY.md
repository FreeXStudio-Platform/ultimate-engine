# Verify a download

Each release has four files: the archive, `manifest.json`, `manifest.json.sig` and `SHA256SUMS`. The manifest names the
archive's SHA-256 and is signed with the FreeXStudio release key.

Key fingerprint: `SHA256:VCd/QHoxBY9Ews0n2WSFc1F89eEMohbp64LvAP4Il/s` (Ed25519). The public key is in [`SIGNING_KEY.pub`](../SIGNING_KEY.pub).

Download the four files into one folder, save `SIGNING_KEY.pub` there, then run:

```sh
ssh-keygen -Y verify -f SIGNING_KEY.pub -I release@freexstudio.com -n ultimate-engine-release -s manifest.json.sig < manifest.json
```

```sh
shasum -a 256 -c SHA256SUMS
```

The first command must say `Good "ultimate-engine-release" signature`. Then check that the SHA-256 of the archive
equals `sha256` in `manifest.json`. If anything differs, do not install it; [tell us privately](../SECURITY.md).

On first installation you are trusting the key you read here. After that, your installed copy trusts only the key inside
it and refuses releases signed by any other.
