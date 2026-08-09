# Install from the air-gap bundle

`dist/hushmark-airgap-0.1.0.tar` contains the three Hushmark images, the Helm chart, verified ONNX
model files, evaluation fixtures, an installer, and a SHA-256 manifest. Dependency installation and
image creation happen before the bundle crosses the offline boundary.

## Build on the connected staging host

```bash
./scripts/build-airgap.sh
sha256sum dist/hushmark-airgap-0.1.0.tar
```

Transfer the tar and its out-of-band digest through the organization's approved media process.

## Verify and load on the offline host

```bash
mkdir hushmark-airgap
tar -xf hushmark-airgap-0.1.0.tar -C hushmark-airgap
cd hushmark-airgap
sha256sum -c SHA256SUMS
./install.sh --load-only
```

For a local offline kind cluster, first create the cluster from an already-seeded kind node image.
The installer then loads the product images directly from the bundle and installs the open-core
evaluation profile with `imagePullPolicy: Never`:

```bash
./install.sh --kind-cluster hushmark-offline --evaluation
```

The acceptance harness performs the complete sequence and rejects any workload image pull event:

```bash
./scripts/e2e-kind.sh --airgap dist/hushmark-airgap-0.1.0.tar
```

For another Kubernetes distribution, import `images.tar` into every node or an approved internal
registry, create the gateway secret, adjust the image repository/tag values, then install
`chart/hushmark-0.1.0.tgz`. The default evaluation key and fake upstream must not be used in
production.

The bundle carries development/evaluation signing evidence only. Validate the delivery digest and
the customer's production signature policy independently.
