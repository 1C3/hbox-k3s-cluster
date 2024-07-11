#!/bin/bash

LOCATION=$1
HOST=$2

ssh root@$HOST '
pushd /etc/wireguard
for i in *.conf; do systemctl disable --now wg-quick@${i%.*}; done
for i in *.conf; do wg-quick down ${i%.*}; done
sleep 2; rm *.conf
popd'

pushd $LOCATION
for i in wg-*; do scp $i root@$HOST:/etc/wireguard/$i; done
for i in stub0.net*; do scp $i root@$HOST:/etc/systemd/network/$i; done
for i in stub0.service; do scp $i root@$HOST:/etc/systemd/system/$i; done
for i in frr*; do scp $i root@$HOST:/etc/frr/frr.conf; done
popd

ssh root@$HOST '
pushd /etc/wireguard
for i in *.conf; do systemctl enable --now wg-quick@${i%.*}; done
for i in *.conf; do systemctl restart wg-quick@${i%.*}; done
popd'

ssh root@$HOST '
systemctl enable --now systemd-networkd
systemctl restart systemd-networkd'

ssh root@$HOST '
systemctl enable --now stub0
systemctl restart stub0'

ssh root@$HOST "
sed -i 's/^ospfd=.*$/ospfd=yes/' /etc/frr/daemons
touch /var/log/frr.log
chown frr:frr /var/log/frr.log
chmod 644 /var/log/frr.log
systemctl enable --now frr
systemctl restart frr"
