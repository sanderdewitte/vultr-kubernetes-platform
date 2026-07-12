# Operations

## Platform status

```bash
kubectl get applications -n argocd
kubectl get pods -A
kubectl get certificates -A
kubectl get clusters.postgresql.cnpg.io -A
kubectl get databases.postgresql.cnpg.io -A
```

## Inspect a specific application

```bash
kubectl get application <name> -n argocd
kubectl describe application <name> -n argocd
```

## Check Traefik

```bash
kubectl get pods -n traefik
kubectl get deployment traefik -n traefik
```

Verify the deployment strategy:

```bash
kubectl get deployment traefik -n traefik   -o jsonpath='{.spec.strategy.type}{"\n"}'
```

Expected:

```text
Recreate
```

Verify redirect arguments:

```bash
kubectl get pod -n traefik   -o jsonpath='{.items[0].spec.containers[0].args}' |
  tr ',' '\n' |
  grep redirections
```

## Test HTTP-to-HTTPS redirect

```bash
curl -I http://auth.example.com
```

Expected:

```text
HTTP/1.1 308 Permanent Redirect
Location: https://auth.example.com/
```

## Check a certificate

```bash
kubectl get certificate -n <namespace>
kubectl describe certificate <certificate-name> -n <namespace>
```

## Worker node maintenance

VKE worker nodes are managed by Vultr.

Do not manually patch worker node operating systems.

After a VKE or node pool replacement:

```bash
cd infra
pulumi preview
pulumi up
```

Pulumi updates DNS if the worker node public IP changed.

## Troubleshooting a Pending hostPort Pod

On a single-node cluster, a replacement Pod may remain Pending if the current Pod already uses the same host ports.

Check:

```bash
kubectl describe pod <pod-name> -n <namespace>
```

Traefik avoids this issue by using a `Recreate` strategy.
