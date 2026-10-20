-- Planet: blur the translucent command surface, not the empty desktop.
hl.layer_rule({ match = { namespace = "^planet$" }, blur = true, ignore_alpha = 0.2 })
