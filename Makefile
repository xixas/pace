# Pace packaging entry point. `make install DESTDIR=/tmp/root PREFIX=/usr`
PREFIX     ?= /usr
DESTDIR    ?=
BINDIR     ?= $(PREFIX)/bin
LIBDIR     ?= $(PREFIX)/lib/pace
DATADIR    ?= $(PREFIX)/share
SYSCONFDIR ?= /etc
PYTHON     ?= /usr/bin/python3
VERSION    ?= $(shell sed -n 's/^Version:[[:space:]]*//p' packaging/rpm/pace.spec)
APPID      := io.github.xixas.Pace
EXT        := pace@osmosys
EXTDIR     := $(DESTDIR)$(DATADIR)/gnome-shell/extensions/$(EXT)
PLASMOID   := $(APPID)
PLASMADIR  := $(DESTDIR)$(DATADIR)/plasma/plasmoids/$(PLASMOID)
VERSION    ?= $(shell sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)

.PHONY: dist installuninstall check lint test

# Source tarball for the rpm: dist/pace-VERSION.tar.gz (tracked files at HEAD)
dist:
	mkdir -p dist
	git archive --format=tar.gz --prefix=pace-$(VERSION)/ -o dist/pace-$(VERSION).tar.gz HEAD

install:
	install -d $(DESTDIR)$(LIBDIR) $(DESTDIR)$(BINDIR) $(EXTDIR) $(PLASMADIR)
	cp -r pace $(DESTDIR)$(LIBDIR)/
	find $(DESTDIR)$(LIBDIR) -name __pycache__ -type d -prune -exec rm -rf {} +
	printf 'VERSION = "%s"\n' "$(VERSION)" > $(DESTDIR)$(LIBDIR)/pace/_version.py
	cp -r extension/$(EXT)/. $(EXTDIR)/
	cp -r plasma/$(PLASMOID)/. $(PLASMADIR)/
	find $(DESTDIR)$(LIBDIR) $(EXTDIR) $(PLASMADIR) -type d -exec chmod 755 {} +
	find $(DESTDIR)$(LIBDIR) $(EXTDIR) $(PLASMADIR) -type f -exec chmod 644 {} +
	printf '#!$(PYTHON)\nimport sys\nsys.path.insert(0, "$(LIBDIR)")\nfrom pace.cli import main\nsys.exit(main())\n' > $(DESTDIR)$(BINDIR)/pace
	printf '#!$(PYTHON)\nimport sys\nsys.path.insert(0, "$(LIBDIR)")\nfrom pace.cli import paced\nsys.exit(paced())\n' > $(DESTDIR)$(BINDIR)/paced
	chmod 755 $(DESTDIR)$(BINDIR)/pace $(DESTDIR)$(BINDIR)/paced
	install -Dm644 data/$(APPID).desktop $(DESTDIR)$(DATADIR)/applications/$(APPID).desktop
	install -Dm644 data/$(APPID).widget.desktop $(DESTDIR)$(DATADIR)/applications/$(APPID).widget.desktop
	install -Dm644 data/$(APPID).daemon.desktop $(DESTDIR)$(SYSCONFDIR)/xdg/autostart/$(APPID).daemon.desktop
	install -Dm644 data/$(APPID).svg $(DESTDIR)$(DATADIR)/icons/hicolor/scalable/apps/$(APPID).svg
	install -Dm644 data/$(APPID)-symbolic.svg $(DESTDIR)$(DATADIR)/icons/hicolor/symbolic/apps/$(APPID)-symbolic.svg
	install -Dm644 data/$(APPID).metainfo.xml $(DESTDIR)$(DATADIR)/metainfo/$(APPID).metainfo.xml

uninstall:
	rm -rf $(DESTDIR)$(LIBDIR) $(EXTDIR) $(PLASMADIR)
	rm -f $(DESTDIR)$(BINDIR)/pace $(DESTDIR)$(BINDIR)/paced \
	  $(DESTDIR)$(DATADIR)/applications/$(APPID).desktop $(DESTDIR)$(DATADIR)/applications/$(APPID).widget.desktop \
	  $(DESTDIR)$(SYSCONFDIR)/xdg/autostart/$(APPID).daemon.desktop \
	  $(DESTDIR)$(DATADIR)/icons/hicolor/scalable/apps/$(APPID).svg \
	  $(DESTDIR)$(DATADIR)/icons/hicolor/symbolic/apps/$(APPID)-symbolic.svg \
	  $(DESTDIR)$(DATADIR)/metainfo/$(APPID).metainfo.xml

check:
	desktop-file-validate data/*.desktop
	appstreamcli validate --no-net data/$(APPID).metainfo.xml

lint:
	ruff check . && ruff format --check .

test:
	python3 -m pytest -q
