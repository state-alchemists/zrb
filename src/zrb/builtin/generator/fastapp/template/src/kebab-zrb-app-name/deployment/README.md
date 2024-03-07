# PascalZrbAppName Deployment

This is a pulumi project containing several helm charts:

- redpanda
- rabbitmq
- postgresql

The helm charts are located at `helm-charts` directory.

# Redownloading helm charts

To re-download the charts, you need to add `redpanda` and `bitnami` to your helm repository.
YOu can do so by invoking the following command:

```bash
# Adding redpanda: https://docs.redpanda.com/docs/deploy/deployment-option/self-hosted/kubernetes/local-guide/
helm repo add redpanda https://charts.redpanda.com
helm repo add jetstack https://charts.jetstack.io

# Adding Signoz https://github.com/SigNoz/charts
helm repo add signoz https://charts.signoz.io

# Adding bitnami
helm repo add bitnami https://charts.bitnami.com/bitnami

helm repo update
```

Once the repo has been updated, you can fetch the repository to `helm-charts` directory by invoking the following command:

```bash
helm fetch redpanda/redpanda --untar --untardir helm-charts
helm fetch bitnami/rabbitmq --untar --untardir helm-charts
helm fetch bitnami/postgresql --untar --untardir helm-charts
helm fetch signoz/signoz --untar --untardir helm-charts
```