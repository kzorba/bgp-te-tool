base: 
  'role:internet-peering':
    - match: pillar
    - bgp-announcements
    - ebgp-peerings
## All minions with a minion_id matching an expression
#   vmx*-lab':
#    - bgp-announcements
#    - ebgp-peerings
