### Setup

- add ssh pubkeys for direct root login
```
cat <<< "<PUBKEY CONTENTS>" > /root/.ssh/authorized_keys
```

- update system and reboot
```
apt update
apt dist-upgrade
reboot
```

- upgrade ubuntu to 24.04
```
do-release-upgrade -d
```

- install needed/useful packages
```
apt install haproxy wireguard-tools frr htop iputils-ping telnet
```

- setup swapfile and zswap
```
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo "/swapfile swap swap defaults 0 0" >> /etc/fstab

cat << EOF > /etc/systemd/system/zswap.service
[Unit]
Description=Enable zswap at boot time
DefaultDependencies=no
Before=basic.target
[Service]
Type=oneshot
ExecStart=echo 1 > /sys/module/zswap/parameters/enabled
ExecStart=echo lz4 > /sys/module/zswap/parameters/compressor
ExecStart=echo z3fold > /sys/module/zswap/parameters/zpool
RemainAfterExit=yes
[Install]
WantedBy=basic.target
EOF

systemctl daemon-reload
systemctl enable --now zswap.service
```

- edit sysctl to disable ipv6 and allow ipv4 forwarding\
```
cat << EOF > /etc/sysctl.conf
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1
net.ipv4.ip_forward = 1
EOF

sysctl -p
```

- add and save iptables rules for traffic over wg interfaces
```
iptables -I INPUT -i wg+ -j ACCEPT
iptables -I INPUT -i ens+ -p udp -m udp --dport 5100:5199 -j ACCEPT
iptables -I INPUT -i ens+ -p tcp --match multiport --dport 2221:2223 -j ACCEPT
iptables -I INPUT -i ens+ -p tcp --dport 8080 -j ACCEPT
iptables -I FORWARD -i wg+ -j ACCEPT
iptables -P FORWARD DROP
iptables-save > /etc/iptables/rules.v4
```
