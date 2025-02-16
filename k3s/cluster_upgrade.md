#### on first node

```
curl -sfL https://get.k3s.io | sh -s - server \
--flannel-iface stub0 \
--bind-address 10.90.0.1 \
--advertise-address 10.90.0.1 \
--node-ip 10.90.0.1 \
--node-external-ip 10.90.0.1 \
--tls-san 10.90.0.1 \
--tls-san 10.90.0.2 \
--tls-san 10.90.0.3 \
--disable-helm-controller \
--disable-cloud-controller \
--disable traefik \
--disable local-storage \
--disable servicelb \
--etcd-arg heartbeat-interval=300 \
--etcd-arg election-timeout=24000
```

#### on second node

```
curl -sfL https://get.k3s.io | sh -s - server \
--flannel-iface stub0 \
--bind-address 10.90.0.2 \
--advertise-address 10.90.0.2 \
--node-ip 10.90.0.2 \
--node-external-ip 10.90.0.2 \
--tls-san 10.90.0.1 \
--tls-san 10.90.0.2 \
--tls-san 10.90.0.3 \
--disable-helm-controller \
--disable-cloud-controller \
--disable traefik \
--disable local-storage \
--disable servicelb \
--etcd-arg heartbeat-interval=300 \
--etcd-arg election-timeout=24000
```

#### on third node

```
curl -sfL https://get.k3s.io | sh -s - server \
--flannel-iface stub0 \
--bind-address 10.90.0.3 \
--advertise-address 10.90.0.3 \
--node-ip 10.90.0.3 \
--node-external-ip 10.90.0.3 \
--tls-san 10.90.0.1 \
--tls-san 10.90.0.2 \
--tls-san 10.90.0.3 \
--disable-helm-controller \
--disable-cloud-controller \
--disable traefik \
--disable local-storage \
--disable servicelb \
--etcd-arg heartbeat-interval=300 \
--etcd-arg election-timeout=24000
```

