#! /usr/bin/env python3

import json
import os
import sys
import ipaddress
import subprocess
import itertools


def generate_wireguard_keys():

    private_key = subprocess.check_output( ["wg", "genkey"] ).decode().strip()
    public_key = subprocess.check_output( ["wg", "pubkey"], input=private_key.encode() ).decode().strip()
    return private_key, public_key


def generate_wireguard_config( link, DATA ):

    host, peer = link[0], link[1]
    hostname, peername = host['HOSTNAME'], peer['HOSTNAME']

    config = ""
    config += "[Interface]\n"
    config += "PrivateKey = {}\n".format( DATA['HOSTS'][hostname]['WG_PRIVKEY'] )
    config += "Address = {}/30\n".format( host['IP'] )

    if DATA['HOSTS'][hostname]["ENDPOINT"]:
        config += "ListenPort = {}\n".format( host['PORT'] )

    for option in DATA['WG_OPTIONS']:
        config += "{}\n".format( option )

    config += "\n[Peer]\n"
    config += "PublicKey = {}\n".format( DATA['HOSTS'][peername]['WG_PUBKEY'] )
    config += "AllowedIPs = {}, {}, 224.0.0.5/32\n".format( DATA['STUBS_NETWORK'], DATA['WG_NETWORK'] )

    if DATA['HOSTS'][peername]["ENDPOINT"]:
        config += "Endpoint = {}:{}\n".format( DATA['HOSTS'][peername]['ENDPOINT'], peer['PORT'] )
        if not DATA['HOSTS'][hostname]["ENDPOINT"]:
            config += "PersistentKeepalive = 10\n"

    return config


def generate_frr_config( hostname, DATA ):

    config = "log file /var/log/frr.log informational\n\n"
    config += "router ospf\n"
    config += "  ospf router-id {}\n".format( DATA['HOSTS'][hostname]['IP'] )
    config += "  network {} area 0\n".format( DATA['STUBS_NETWORK'] )
    config += "  network {} area 0\n".format( DATA['WG_NETWORK'] )
    config += "  passive-interface default\n"
    config += "  redistribute static\n\n"

    for interface in DATA['HOSTS'][hostname]['WG_LINKS']:
        config += "interface {}\n".format( interface )
        config += "  no ip ospf passive\n"
        config += "  ip ospf network point-to-point\n\n"

    return config


def generate_stub_config( hostname, DATA, filetype ):

    if filetype == 'netdev':
        config = "[NetDev]\n"
        config += "Name=stub0\n"
        config += "Kind=dummy\n"
    elif filetype == 'network':
        config = "[Match]\n"
        config += "Name=stub0\n\n"
        config += "[Network]\n"
        config += "Address={}/32\n".format( DATA['HOSTS'][hostname]['IP'] )
        config += "LinkLocalAddressing=no\n"
        config += "IPv6AcceptRA=no\n\n"
        config += "[Route]\n"
        config += "Destination={}/32\n".format( DATA['HOSTS'][hostname]['IP'] )
        config += "Scope=link\n"
    elif filetype == 'iptables':
        config = "[Unit]\n"
        config += "Description=Iptables rules for stub0 source ip to be used over all wg* interfaces \n"
        config += "After=network.target\n\n"
        config += "[Service]\n"
        config += "Type=oneshot\n"
        config += "RemainAfterExit=yes\n"
        config += "ExecStart=/bin/sh -c 'iptables -t mangle -A OUTPUT -o wg+ ! -p ospf -j MARK --set-mark 1; iptables -t nat -A POSTROUTING -m mark --mark 1 -j SNAT --to-source {}'\n".format( DATA['HOSTS'][hostname]['IP'] )
        config += "ExecStop=/bin/sh -c 'iptables -t mangle -D OUTPUT -o wg+ ! -p ospf -j MARK --set-mark 1; iptables -t nat -D POSTROUTING -m mark --mark 1 -j SNAT --to-source {}'\n\n".format( DATA['HOSTS'][hostname]['IP'] )
        config += "[Install]\n"
        config += "WantedBy=multi-user.target\n"

    return config


def main( config_file ):

    with open( config_file, 'r' ) as f:
        DATA = json.load(f)
    os.makedirs( "configs", exist_ok=True )
    for hostname in DATA['HOSTS']:
        os.makedirs( f"configs/{hostname}", exist_ok=True )

    stub_network = [ str(ip) for ip in ipaddress.ip_network( DATA['STUBS_NETWORK'] ).hosts() ]
    wg_network = list( ipaddress.ip_network( DATA['WG_NETWORK'] ).subnets( new_prefix=30 ) )
    port_range = [ *range( int( DATA['PORT_RANGE'].split("-")[0] ), int( DATA['PORT_RANGE'].split("-")[1] ) + 1 ) ]

    for hostname in DATA['HOSTS']:
        DATA['HOSTS'][hostname]['IP'] = stub_network.pop(0)
        DATA['HOSTS'][hostname]['WG_PRIVKEY'], DATA['HOSTS'][hostname]['WG_PUBKEY'] = generate_wireguard_keys()
        DATA['HOSTS'][hostname]['WG_LINKS'] = []

    DATA['WG_PTP_LINKS'] = []
    for host1, host2 in itertools.combinations( DATA['HOSTS'], 2 ):
        if DATA['HOSTS'][host1]["ENDPOINT"] or DATA['HOSTS'][host2]["ENDPOINT"]:
            address1, address2 = [ str(ip) for ip in wg_network.pop(0).hosts() ]
            link = [
                {
                    'HOSTNAME' : host1,
                    'IP': address1
                },
                {
                    'HOSTNAME' : host2,
                    'IP': address2
                }
            ]
            if DATA['HOSTS'][host1]['ENDPOINT']:
                link[0]['PORT'] = port_range.pop(0)
            if DATA['HOSTS'][host2]['ENDPOINT']:
                link[1]['PORT'] = port_range.pop(0)
            DATA['WG_PTP_LINKS'].append( link )

    with open( 'configs/full_config.json', 'w' ) as f:
        json.dump( DATA, f, indent=2 )

    for link in DATA['WG_PTP_LINKS']:
        hostname, peername = link[0]['HOSTNAME'], link[1]['HOSTNAME']
        with open( 'configs/{}/wg-{}-{}.conf'.format( hostname, hostname, peername ), 'w' ) as f:
            f.write( generate_wireguard_config( link, DATA ) )
            DATA['HOSTS'][hostname]['WG_LINKS'].append( 'wg-{}-{}'.format( hostname, peername ) )
        with open( 'configs/{}/wg-{}-{}.conf'.format( peername, peername, hostname ), 'w' ) as f:
            f.write( generate_wireguard_config( list( reversed( link ) ), DATA ) )
            DATA['HOSTS'][peername]['WG_LINKS'].append( 'wg-{}-{}'.format( peername, hostname ) )

    for hostname in DATA['HOSTS']:
        with open( 'configs/{}/frr.conf'.format( hostname ), 'w' ) as f:
            f.write( generate_frr_config( hostname, DATA ) )
        with open( 'configs/{}/stub0.netdev'.format( hostname ), 'w' ) as f:
            f.write( generate_stub_config( hostname, DATA, 'netdev' ) )
        with open( 'configs/{}/stub0.network'.format( hostname ), 'w' ) as f:
            f.write( generate_stub_config( hostname, DATA, 'network' ) )
        with open( 'configs/{}/stub0.service'.format( hostname ), 'w' ) as f:
            f.write( generate_stub_config( hostname, DATA, 'iptables' ) )


if __name__ == "__main__":
    if not os.path.exists(sys.argv[1]):
        print("Usage: python script.py <config_file>")
        sys.exit(1)
    main(sys.argv[1])
