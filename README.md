# Gremnix

_Gremnix_ is a tool to interactively browse the references graph of Nix store paths.

**!!! Gremnix uses the `--graphml` option of `nix-store --query` command which is not yet merged:/ !!!**

It is based on the console of [Gremlin](http://tinkerpop.apache.org/),
a powerful graph traversal language.


The following Gremlin session shows how to
- get the roots of the graph
- count output paths of the closure of the `docker` output path
- list the 5 biggest output paths of this closure (print the size and the path)

```
$ gremnix /nix/store/ji0h0kgayxrdy7aj0bxxxi8b5sc8mp6x-docker-18.03.1-ce /nix/store/m16yg0mdipp48mk0bia19xnk4wyqa9x7-vim-8.0.1451
         \,,,/
         (o o)
-----oOOo-(3)-oOOo-----

gremlin> g.root()
  ==>v[/nix/store/ji0h0kgayxrdy7aj0bxxxi8b5sc8mp6x-docker-18.03.1-ce]
  ==>v[/nix/store/m16yg0mdipp48mk0bia19xnk4wyqa9x7-vim-8.0.1451]
gremlin> g.root().byName("docker").closure().count()
  ==>146
gremlin> g.root().closure().order().by("narSize", decr).as("n").values("narSize").mb().as("s").select("s","n").limit(5)
  ==>[s:245.682912,n:v[/nix/store/8gyv6sms33szh2w7wlbyqly3fkki690j-go-1.9.5]]
  ==>[s:208.389136,n:v[/nix/store/b0zlxla7dmy1iwc3g459rjznx59797xy-binutils-2.28.1]]
  ==>[s:198.754944,n:v[/nix/store/gnz7xgrh04jarccmc2in0panz7c6lxya-systemd-237]]
  ==>[s:131.941768,n:v[/nix/store/bm7pb1s7rx1ad80706b5xqrznq7fgpgx-gcc-7.3.0]]
  ==>[s:65.868984,n:v[/nix/store/839jh51k7lsb27bw7x4ig9md8kpk65sj-docker-containerd]]
```

There are much more Gremlin steps which are well
[documented](http://tinkerpop.apache.org/docs/current/reference/#graph-traversal-steps).
