[Skip to main content](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/kubernetes-advanced/#__docusaurus_skipToContent_fallback)

[![InfinyOn Logo](https://www.fluvio.io/img/infinyon-gradient.png)](https://www.fluvio.io/)[Fluvio](https://www.fluvio.io/docs/latest/fluvio/quickstart) [SDF](https://www.fluvio.io/sdf/quickstart) [Cloud](https://www.fluvio.io/docs/latest/cloud/quickstart) [Connectors](https://www.fluvio.io/docs/latest/connectors/overview) [SmartModules](https://www.fluvio.io/docs/latest/smartmodules/quickstart) [Hub](https://www.fluvio.io/docs/latest/hub/overview)

[latest](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/kubernetes-advanced)

- [latest](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/kubernetes-advanced)
- [0.18.1 (stable)](https://www.fluvio.io/docs/fluvio/installation/advanced/kubernetes-advanced)
- [0.18.0](https://www.fluvio.io/docs/0.18.0/fluvio/installation/advanced/kubernetes-advanced)
- [0.17.3](https://www.fluvio.io/docs/0.17.3/fluvio/installation/advanced/kubernetes-advanced)
- [0.17.2](https://www.fluvio.io/docs/0.17.2/fluvio/installation/advanced/kubernetes-advanced)
- [0.17.0](https://www.fluvio.io/docs/0.17.0/fluvio/installation/advanced/kubernetes-advanced)
- [0.16.1](https://www.fluvio.io/docs/0.16.1/fluvio/installation/advanced/kubernetes-advanced)
- [0.15.2](https://www.fluvio.io/docs/0.15.2/fluvio/installation/advanced/kubernetes-advanced)
- [0.15.1](https://www.fluvio.io/docs/0.15.1/fluvio/installation/advanced/kubernetes-advanced)
- [0.15.0](https://www.fluvio.io/docs/0.15.0/fluvio/installation/advanced/kubernetes-advanced)
- [0.14.1](https://www.fluvio.io/docs/0.14.1/fluvio/installation/advanced/kubernetes-advanced)
- [0.14.0](https://www.fluvio.io/docs/0.14.0/fluvio/installation/advanced/kubernetes-advanced)
- [0.13.0](https://www.fluvio.io/docs/0.13.0/fluvio/installation/advanced/kubernetes-advanced)
- [0.12.0](https://www.fluvio.io/docs/0.12.0/fluvio/installation/advanced/kubernetes-advanced)
- [0.11.12](https://www.fluvio.io/docs/0.11.12/fluvio/installation/advanced/kubernetes-advanced)
- [0.11.11](https://www.fluvio.io/docs/0.11.11/fluvio/installation/advanced/kubernetes-advanced)

[![GitHub stars](https://img.shields.io/github/stars/infinyon/fluvio?style=social)](https://github.com/infinyon/fluvio/)

`ctrl`  `K`

- Fluvio
- [Quickstart](https://www.fluvio.io/docs/latest/fluvio/quickstart)
- [Overview](https://www.fluvio.io/docs/latest/fluvio/overview)
- [Install Guide](https://www.fluvio.io/docs/latest/fluvio/installation/)

  - [Local](https://www.fluvio.io/docs/latest/fluvio/installation/local)
  - [Docker](https://www.fluvio.io/docs/latest/fluvio/installation/docker)
  - [Kubernetes](https://www.fluvio.io/docs/latest/fluvio/installation/kubernetes)
  - [Advanced](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/kubernetes-advanced/#)

    - [Docker: Custom App Container](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/docker-custom-clients)
    - [Kubernetes: Helm & More](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/kubernetes-advanced)
- [Tutorials](https://www.fluvio.io/docs/latest/fluvio/tutorials/)

  - [HTTP Source -> Topic](https://www.fluvio.io/docs/latest/fluvio/tutorials/http-source)
  - [Connector Transformations](https://www.fluvio.io/docs/latest/fluvio/tutorials/connector-transformations)
  - [Topic -> SQL Sink](https://www.fluvio.io/docs/latest/fluvio/tutorials/sql-sink)
  - [Mirroring - Raspberry Pi to Cluster](https://www.fluvio.io/docs/latest/fluvio/tutorials/mirroring-iot-local)
  - [Mirroring - Cluster to Cluster](https://www.fluvio.io/docs/latest/fluvio/tutorials/mirroring-two-clusters)
- [Concepts](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/kubernetes-advanced/#)

- [CLI](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/kubernetes-advanced/#)

- [FVM](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/kubernetes-advanced/#)

- [Client APIs](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/kubernetes-advanced/#)

- [Configuration Defaults](https://www.fluvio.io/docs/latest/fluvio/config-defaults)
- [Troubleshooting](https://www.fluvio.io/docs/latest/fluvio/troubleshooting)
- [News](https://www.fluvio.io/news)

fluvio@latest

This is unreleased documentation for Fluvio **latest** version.

For up-to-date documentation, see the **[latest version](https://www.fluvio.io/docs/fluvio/installation/advanced/kubernetes-advanced)** (0.18.1 (stable)).

- [Home page](https://www.fluvio.io/)
- [Install Guide](https://www.fluvio.io/docs/latest/fluvio/installation/)
- Advanced
- Kubernetes: Helm & More

Version: latest

On this page

# Kubernetes: Helm & More

Fluvio is a Kubernetes-native containerized application. There are multiple
ways to install Fluvio in a kubernetes cluster. Fluvio CLI is a tool to manage
Fluvio's installation, or the helm charts can be used directly.

Installing with the cli will install a simple default configuration for many
types of kubernetes clusters. If you only want to install a single instance of
Fluvio, Fluvio will automatically install and run the Fluvio service.

However, if you want a particular networking configuration, or wish to install multiple instances of Fluvio, you should install the helm chart manually (modifying them for your needs).

If you run into any problems along the way, make sure to check out our [troubleshooting](https://www.fluvio.io/docs/latest/fluvio/troubleshooting) page to find a fix.

## Install with the CLI [​](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/kubernetes-advanced/\#install-with-the-cli "Direct link to Install with the CLI")

This command will install Fluvio and it's dependencies in the default namespace. This method works with many but not all kubernetes cluster types and is an opinionated set of configurations for a simple, working fluvio cluster.

```shell
$ fluvio cluster start --k8
```

For installing on a remote Kubernetes cluster where the machine running the CLI is not the local host, consider using the `--proxy-addr <DNS or IP>` option which will access the fluvio app endpoints through the specified proxy address.

```shell
$ fluvio cluster start --k8 --proxy-addr <DNS or IP>
```

## Install a fluvio instance with Helm [​](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/kubernetes-advanced/\#install-a-fluvio-instance-with-helm "Direct link to Install a fluvio instance with Helm")

If you want more precise control of the kubernetes installation, you need to install the charts manually. Helm needs access
to a working `kubectl` context. The charts are available in the [fluvio repository](https://github.com/infinyon/fluvio) under [`k8-util/helm/`](https://github.com/infinyon/fluvio/tree/master/k8-util/helm).

There are two charts. First is the `fluvio-sys` chart which is common to all Fluvio instances. Second is a `fluvio-app` chart which can be configured for one or more instances of clusters

```bash
helm upgrade --install fluvio-sys ./k8-util/helm/fluvio-sys
```

```shell
helm install fluvio-app k8-util/helm/fluvio-app  --values ./k8-util/helm/fluvio-app/values.yaml \
  --set "image.tag=0.11.5" \
  --set "scPod.nodePort=30003"

fluvio profile add k1 127.0.0.1:30003
fluvio cluster create spg default
```

## Install a Multi Cluster Instance with Helm [​](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/kubernetes-advanced/\#install-a-multi-cluster-instance-with-helm "Direct link to Install a Multi Cluster Instance with Helm")

You can install multiple Fluvio instances on the same Kubernetes cluster by using different namespaces. In order to do so, you need to specify the namespace when installing Fluvio otherwise Fluvio will install in the default namespace. The charts are available in the [fluvio repository](https://github.com/infinyon/fluvio) under [`k8-util/helm/`](https://github.com/infinyon/fluvio/tree/master/k8-util/helm).

Other networking configurations besides nodePort configuration are beyond
the scope of this guide and require modification of the helm chart values. Feel free to ask about other configurations on our [Discord](https://discordapp.com/invite/bBG2dTz) or on the Fluvio repository [discussions](https://github.com/infinyon/fluvio/discussions).

First, install the `fluvio-sys` chart. This only has to be done once.

```bash
helm upgrade --install fluvio-sys ./k8-util/helm/fluvio-sys
```

Then install each instance of Fluvio one by one on a different namespace and spacing
the scPod ports apart.

Depending on the implementation of the kubernetes cluster being used,
the `fluvio profile add NAME  HOST:PORT`, the host might be a dns name,
local host, or an IP. The example below assumes a local host access to
the NodePort, and a copy of the [fluvio repository](https://github.com/infinyon/fluvio).

First instance:

```shell
kubectl create namespace first
helm install fluvio-app k8-util/helm/fluvio-app  --values ./k8-util/helm/fluvio-app/values.yaml \
  --namespace third \
  --set "image.tag=0.11.5" \
  --set "scPod.nodePort=30003"

fluvio profile add k1 127.0.0.1:30003
fluvio cluster create spg default
```

Second instance:

```shell
kubectl create namespace second
helm install fluvio-app k8-util/helm/fluvio-app  --values ./k8-util/helm/fluvio-app/values.yaml \
  --namespace third \
  --set "image.tag=0.11.5" \
  --set "scPod.nodePort=30103"

fluvio profile add k2 127.0.0.1:30103
fluvio cluster create spg default
```

and so forth.

To delete a Fluvio instances, supply namespace as an argument.

```shell
$ fluvio cluster delete --k8 --namespace first
```

You can only a delete `fluvio-sys` chart when you have deleted all the Fluvio instances.

## Resource config with direct CRD specs [​](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/kubernetes-advanced/\#resource-config-with-direct-crd-specs "Direct link to Resource config with direct CRD specs")

Fluvio resources are generally mapped to Kubernetes CRDs. Specific cluster configurations
can be packaged as a set of kubectl specs and configuration controlled. See samples of configuring in the [Fluvio CRD Samples](https://github.com/infinyon/fluvio/tree/master/k8-util/samples/crd) in the Fluvio repository.

[Edit this page](https://github.com/infinyon/fluvio-docs/tree/main/docs/fluvio/installation/advanced/kubernetes-advanced.mdx)

Last updated on **Jul 9, 2025** by **Felipe Cardozo**

[Previous\\
\\
Docker: Custom App Container](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/docker-custom-clients) [Next\\
\\
Tutorials](https://www.fluvio.io/docs/latest/fluvio/tutorials/)

- [Install with the CLI](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/kubernetes-advanced/#install-with-the-cli)
- [Install a fluvio instance with Helm](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/kubernetes-advanced/#install-a-fluvio-instance-with-helm)
- [Install a Multi Cluster Instance with Helm](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/kubernetes-advanced/#install-a-multi-cluster-instance-with-helm)
- [Resource config with direct CRD specs](https://www.fluvio.io/docs/latest/fluvio/installation/advanced/kubernetes-advanced/#resource-config-with-direct-crd-specs)

Fluvio

- [Docs](https://www.fluvio.io/docs/fluvio/quickstart)
- [FAQs](https://www.fluvio.io/faqs)
- [News](https://www.fluvio.io/news)

Community

- [Discord](https://discordapp.com/invite/bBG2dTz)
- [Twitter](https://twitter.com/infinyon)
- [GitHub](https://github.com/InfinyOn/fluvio)
- [YouTube](https://www.youtube.com/@InfinyOn/videos)

Copyright © 2025 InfinyOn, Inc. All rights reserved.