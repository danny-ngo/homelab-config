"""Small, dependency-free filters for inventory network safety checks."""
from ipaddress import ip_network

def cidr(value): return ip_network(str(value), strict=False)
def cidr_valid(value):
    try: cidr(value); return True
    except ValueError: return False
def cidr_overlaps(left, right): return cidr(left).overlaps(cidr(right))
class FilterModule:
    def filters(self): return {"cidr_valid": cidr_valid, "cidr_overlaps": cidr_overlaps}
