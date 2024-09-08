#### Setup information for my k3s cluster

*This repo is not meant as a tutorial, but it's open in case someone wants to take a look at the configs to help build their own thing.*

The main objective for this cluster was to make the nodes easy to distribute geographically on different home networks, without requiring any additional configuration.
The secure boot chain, full disk encryption and firewall rules ensure that data on the nodes is reasonably safe even if they are not in a physically secure location.
Thanks to a pretty cool wireguard/ospf vpn configuration, the nodes can be turned off on a network, moved to another, and they will reconnect and rebuild routes on their own, while the gateways are highly available

- **Frontend**:
  - 2x free VM.Standard.E2.1.Micro instances on Oracle Cloud (1X OCPU, 1GB RAM, 50GB Disk)
  - Ubuntu 24.04 Minimal
  - DNS load balancing between the two nodes
  - HaProxy
- **Backend**:
  - 3x Chuwi Herobox mini PCs (Intel N100, 8GB RAM, 250GB SSD)
  - Gentoo Stable
  - Full disk encryption using keys held in the TPM module and unlocked on successful secure boot
  - Direct EFI boot of a Unified Kernel Image with self-signed secure boot keys
  - Lightweight k3s config
- **Backend Network**:
  - Wireguard VPN, both frontend servers are the gateways
  - Wireguard point-to-point links connecting every gateway to every other host
  - FRR running OSPF over the wg network to propagate routes, provide load balancing and automatic failover
  - All hosts have a stub0 interface that acts as their primary IP address for routing
  - Outgoing packets on wg interfaces get source IP changed to the host's stub0 IP through iptables
  - Configs generated through a python script
- **Firewall**:
  - Iptables blocking most input traffic on the hosts, except packets coming from wireguard interfaces
  - Iptables on the frontends also blocking forwarding of packets not coming through wireguard

Future improvements:
- Proxying all internet traffic from the hboxes through the gateways, to minimize exposure to the local network
- Configuring a distributed storage system for the cluster, possibly piraeus (higher performance) or longhorn
- Automatic update of dns entries in case one of the frontends fails
