"""Small, dependency-free filters for inventory network safety checks."""
from ipaddress import IPv4Address, ip_network

def cidr(value): return ip_network(str(value), strict=False)
def cidr_valid(value):
    try: cidr(value); return True
    except ValueError: return False
def cidr_overlaps(left, right): return cidr(left).overlaps(cidr(right))
def cidr_prefix(value): return cidr(value).prefixlen
def ipv4_address_valid(value):
    try: IPv4Address(str(value)); return True
    except ValueError: return False
class FilterModule:
    def filters(self):
        return {
            "cidr_valid": cidr_valid,
            "cidr_overlaps": cidr_overlaps,
            "cidr_prefix": cidr_prefix,
            "ipv4_address_valid": ipv4_address_valid,
        }
