proxy:
  proxytype: napalm
  driver: junos
  host: 172.18.0.13
  timeoute: 300
  username: salty
  password: ''
  optional_args:
    key_file: /u/napalm-ssh-keys/salty_id_ecdsa
role: [ pe, internet-peering, internet-transit ]
site: [ mf ]

