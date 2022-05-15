Configure eBGP peerings:
  netconfig.managed:
    - template_name: salt://ebgp-peerings/templates/peerings.j2
    - debug: false
#    - context:
#        test: {{ pillar.get('announcements') | json }}
