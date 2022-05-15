Configure BGP announcements:
  netconfig.managed:
    - template_name: salt://bgp-announcements/templates/announcements.j2
    - debug: false
#    - context:
#        test: {{ pillar.get('announcements') | json }}
