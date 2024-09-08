### disk setup

- use fdisk to format disk as gpt, create one partion of type 1 (EFI System Partition) and another of type 23 (Linux Root x86_64):
```
blkdiscard -f /dev/sda
fdisk /dev/sda
g
n +1G t 1
n t 23
w
```

- format and open root partition luks device:
```
cryptsetup luksFormat /dev/sda2
cryptsetup luksOpen /dev/sda2 root
cryptsetup refresh --allow-discards --persistent /dev/mapper/root
```

- format filesystems:
```
mkfs.vfat -F32 -n ESP /dev/sda1
mkfs.ext4 -L ROOT -O fast_commit /dev/mapper/root
```

- mount partitions:
```
mkdir /mnt/gentoo
mount /dev/mapper/root /mnt/gentoo
mkdir /mnt/gentoo/efi
mount /dev/sda1 /mnt/gentoo/efi
```

### system install

- download and extract the desired stage tarball from https://www.gentoo.org/downloads/, check checksum and extract the files
```
cd /mnt/gentoo
wget https://distfiles.gentoo.org/releases/amd64/autobuilds/20240514T170404Z/stage3-amd64-nomultilib-systemd-20240514T170404Z.tar.xz
wget https://distfiles.gentoo.org/releases/amd64/autobuilds/20240514T170404Z/stage3-amd64-nomultilib-systemd-20240514T170404Z.tar.xz.DIGESTS
sha512sum stage3*.tar.xz
cat stage3*.DIGESTS | grep -i -A 1 sha512
tar xpvf stage3*.tar.xz --xattrs-include='*.*' --numeric-owner
```

- chroot into the new system:
```
cp --dereference /etc/resolv.conf /mnt/gentoo/etc/
arch-chroot /mnt/gentoo
```

- edit **etc/portage/make.conf** of the new system:
```
cat <<EOF > /etc/portage/make.conf
GENTOO_MIRRORS="https://gentoo.mirror.garr.it http://distfiles.gentoo.org"

COMMON_FLAGS="-march=native -O3 -flto -pipe -falign-functions=32 -fno-semantic-interposition"
CFLAGS="${COMMON_FLAGS}"
CXXFLAGS="${COMMON_FLAGS}"
FCFLAGS="${COMMON_FLAGS}"
FFLAGS="${COMMON_FLAGS}"
GOAMD64="v3"
CPU_FLAGS_X86="aes avx avx2 f16c fma3 mmx mmxext pclmul popcnt rdrand sha sse sse2 sse3 sse4_1 sse4_2 ssse3 vpclmulqdq"

MAKEOPTS="-j2 -l2"
FEATURES="binpkg-request-signature"

LC_MESSAGES=C.utf8
ACCEPT_LICENSE="*"
VIDEO_CARDS="intel"
USE="lto"
EOF
```

- edit **/etc/portage/binrepos.conf/gentoobinhost.conf**:
```
cat <<EOF > /etc/portage/binrepos.conf/gentoobinhost.conf
[garr]
priority = 10
sync-uri = https://gentoo.mirror.garr.it/releases/amd64/binpackages/23.0/x86-64-v3

[gentoo-cdn]
priority = 1
sync-uri = https://distfiles.gentoo.org/releases/amd64/binpackages/23.0/x86-64-v3
EOF
```

- add **package.env**:
```
mkdir -p /etc/portage/env

cat <<EOF > /etc/portage/env/binpkg
FEATURES="getbinpkg binpkg-request-signature"
USE="-lto"
EOF

cat <<EOF > /etc/portage/package.env
sys-devel/gcc binpkg
EOF
```

- edit **package.use**:
```
rm -r /etc/portage/package.use/
cat <<EOF >> /etc/portage/package.use
sys-apps/systemd cryptsetup boot tpm
sys-kernel/installkernel dracut uki
net-wireless/iwd standalone -systemd
EOF
```

- update gentoo trusted keys and install packages:
```
emerge-webrsync
getuto
emerge -1 -g gcc
emerge -quDN @world htop gentoo-kernel-bin linux-firmware intel-microcode sbctl efibootmgr iwd tpm2-tools frr wireguard-tools telnet-bsd
```

- set root passwd:
```
passwd
```

### kernel install

- edit /etc/dracut.conf to ensure crypto modules are included in initramfs, and kernel cmdline is properly set by adding:
```
LUKS_ID=$( blkid | grep /dev/sda2 | sed -r 's/.* UUID="(\S*)".*/\1/' )
ROOT_ID=$( blkid | grep /dev/mapper/root | sed -r 's/.* UUID="(\S*)".*/\1/' )

cat <<EOF > /etc/dracut.conf
add_dracutmodules+=" crypt tpm2-tss "
kernel_cmdline="root=UUID=$ROOT_ID rd.luks.uuid=$LUKS_ID"
use_fstab="yes"
early_microcode="yes"
add_drivers+=" i915 "
#hostonly="yes"
EOF
```

- configure **/etc/fstab**:
```
cat <<EOF >> /etc/fstab
UUID=$ROOT_ID  /     ext4  defaults,noatime,discard  0 1
LABEL=ESP      /efi  vfat  defaults,noatime          0 2
EOF
```

- use sbctl to generate and enroll uefi signing keys, add keys location to dracut to sign UKI:
```
sbctl status
sbctl create-keys
sbctl enroll-keys --yes-this-might-brick-my-machine
sbctl status
```

- rebuild dracut initramfs and UKI by reinstalling gentoo-kernel-bin:
```
emerge --config gentoo-kernel-bin
```

### efistub setup

- delete existing boot entries, create uki boot entry
```
for i in $(efibootmgr | grep -E -o "^Boot[0-9]{4}" | cut -c 5-8);
    do efibootmgr -b $i -B -q;
done
UKI_PRIMARY=$( ls -t1 /efi/EFI/Linux/ | head -n1 )
efibootmgr --create --disk /dev/sda --label "Gentoo Primary EFI Stub UKI" --loader "\EFI\Linux\\${UKI_PRIMARY}"
```

### cleanup

- remove stage3:
```
rm /stage3-amd64-*
```

exit chroot an unmount everything:
```
exit
cd
umount -lR /mnt/gentoo
```

- reboot

### after reboot

- set systemd options:
```
ln -sf ../usr/share/zoneinfo/Europe/Rome /etc/localtime
systemd-machine-id-setup
systemd-firstboot
systemctl preset-all
localectl set-keymap it
```

- enable resolved and iwd:
```
cat <<EOF > /etc/resolv.conf
nameserver 1.1.1.1
nameserver 8.8.8.8
EOF

systemctl enable systemd-timesyncd
systemctl enable sshd
```

- connect to wireless network:
```
cat <<EOF > /etc/iwd/main.conf
[General]
EnableNetworkConfiguration=true
EOF

systemctl enable --now iwd
iwctl
station wlan0 connect <NETWORK NAME>
```

- configure systemd-networkd for auto dhcp on wired and wireless interface:
```
cat <<EOF >> /etc/systemd/network/50-wired-dhcp.network
[Match]
Name=enp1s0

[Network]
DHCP=yes
EOF

cat <<EOF >> /etc/systemd/network/60-wlan0-dhcp.network
[Match]
Name=wlan0

[Network]
DHCP=yes
IgnoreCarrierLoss=3s
EOF

systemctl enable --now systemd-networkd.service
```

- configure systemd-networkd-wait-online to be up with any interface:
```
systemctl edit systemd-networkd-wait-online.service

[Service]
ExecStart=
ExecStart=/usr/lib/systemd/systemd-networkd-wait-online --any
```

- allow ssh root login:
```
nano /etc/ssh/sshd_config
systemctl restart sshd
```

- setup tpm2 key for LUKS unlocking:
```
systemd-cryptenroll --tpm2-device=list
systemd-cryptenroll --tpm2-device=/dev/tpmrm0 --tpm2-pcrs=0+2+7 /dev/sda2
```

- update /etc/dracut.conf to ensure crypto modules are included in initramfs, and kernel cmdline is properly set by adding:
```
LUKS_ID=$( blkid | grep /dev/sda2 | sed -r 's/.* UUID="(\S*)".*/\1/' )
ROOT_ID=$( blkid | grep /dev/mapper/root | sed -r 's/.* UUID="(\S*)".*/\1/' )

cat /etc/dracut.conf | sed "s/^kernel_cmdline=.*$/kernel_cmdline=\"root=UUID=$ROOT_ID rd.luks.uuid=$LUKS_ID rd.luks.options=$LUKS_ID=tpm2-device=auto fsck.mode=force fsck.repair=yes\"/"

emerge --config gentoo-kernel-bin
```

- update boot entries:
```
cat <<EOF > /boot/kupdate.sh
#!/bin/bash

for i in $(efibootmgr | grep -E -o "^Boot[0-9]{4}" | cut -c 5-8);
    do efibootmgr -b $i -B -q;
done
efibootmgr -O -q

UKI_PRIMARY=$( ls -t1 /efi/EFI/Linux/ | head -n1 )
UKI_SECONDARY=$( ls -t1 /efi/EFI/Linux/ | head -n2 | tail -n1 )

efibootmgr --create --disk /dev/sda --label "Gentoo Primary EFI Stub UKI" --loader "\EFI\Linux\\${UKI_PRIMARY}" -q
efibootmgr --create --disk /dev/sda --label "Gentoo Secondary EFI Stub UKI" --loader "\EFI\Linux\\${UKI_SECONDARY}" -q
efibootmgr -o 0000,0001

efibootmgr
EOF

chmod 700 /boot/kupdate.sh
. /boot/kupdate.sh
```

- if boots are working ok, remove ability for dracut to drop to root shell in case of failed boot by adding `panic=0` to cmdline

### on service host

- create and push ssh keys for remote login:
```
ssh-keygen -C "hbox" -f ~/.ssh/hbox
ssh-copy-id -i hbox root@<IP>
```

### iptables configs

- create iptables rules systemd service
```
cat <<EOF > /etc/systemd/system/wg-rules.service
[Unit]
Description=iptables rules to drop most input not coming from wg* interfaces
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c '\
    iptables -P INPUT DROP; \
    iptables -I INPUT -i lo -j ACCEPT; \
    iptables -I INPUT -i wg+ -j ACCEPT; \
    iptables -I INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT; \
    iptables -I INPUT -p tcp --dport 22 -j ACCEPT; \
    iptables -I INPUT -p icmp --icmp-type 8 -j ACCEPT'

ExecStop=/bin/sh -c '\
    iptables -P INPUT ACCEPT; \
    iptables -D INPUT -i lo -j ACCEPT; \
    iptables -D INPUT -i wg+ -j ACCEPT; \
    iptables -D INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT; \
    iptables -D INPUT -p tcp --dport 22 -j ACCEPT; \
    iptables -D INPUT -p icmp --icmp-type 8 -j ACCEPT'

[Install]
WantedBy=multi-user.target
EOF
```

- enable the script
```
systemctl enable --now wg-rules
```
