Name:           pace
Version:        0.1.8
Release:        1%{?dist}
Summary:        PineStem billed hours against the weekly target, on the panel
License:        MIT
URL:            https://github.com/xixas/pace
Source0:        pace-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  make
BuildRequires:  desktop-file-utils
Requires:       python3 >= 3.11
Requires:       python3-gobject
Requires:       python3-cairo
Requires:       gtk4
Requires:       libadwaita
Requires:       libsecret

%description
Pace shows your PineStem billed hours for the week against your target and the
loss-of-pay line: a GNOME Shell panel extension, a tray icon on other desktops,
a mini widget and a dashboard. Includes the paced background service.

%prep
%autosetup

%build

%install
make install DESTDIR=%{buildroot} PREFIX=%{_prefix} SYSCONFDIR=%{_sysconfdir}

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/*.desktop

# No %postun on purpose. Removing the package never touches files in a home
# directory (design C11): the keyring entry, ~/.local/state/pace, ~/.config/pace
# and ~/.config/autostart stay. "Remove my Pace data" in Preferences deletes them.
# A new GNOME Shell extension is only seen after the next login.

%files
%{_bindir}/pace
%{_bindir}/paced
%{_prefix}/lib/pace/
%{_datadir}/gnome-shell/extensions/pace@osmosys/
%{_datadir}/plasma/plasmoids/io.github.xixas.Pace/
%{_datadir}/applications/io.github.xixas.Pace.desktop
%{_datadir}/applications/io.github.xixas.Pace.widget.desktop
%config(noreplace) %{_sysconfdir}/xdg/autostart/io.github.xixas.Pace.daemon.desktop
%{_datadir}/icons/hicolor/scalable/apps/io.github.xixas.Pace.svg
%{_datadir}/icons/hicolor/symbolic/apps/io.github.xixas.Pace-symbolic.svg
%{_datadir}/metainfo/io.github.xixas.Pace.metainfo.xml

%changelog
* Thu Nov 26 2026 Vishnu Kyatannawar <vishnu.k@osmosys.co> - 0.1.8-1
- GNOME: dropdown titles and project names are full white again, not the Shell's greyed-out text

* Mon Nov 23 2026 Vishnu Kyatannawar <vishnu.k@osmosys.co> - 0.1.7-1
- KDE Plasma 6 panel widget with the GNOME indicator and menu; the tray steps aside while it's on a panel
- KDE: the mini widget stays above other windows on every desktop (a KWin rule)
- A locked KWallet at login no longer blocks paced ("Waiting for the wallet")

* Mon Nov 16 2026 Vikas Kyatannawar <vikas.k@osmosys.co> - 0.1.6-1
- Arch / CachyOS package (.pkg.tar.zst) on every release

* Mon Nov 16 2026 Vikas Kyatannawar <vikas.k@osmosys.co> - 0.1.5-1
- KDE Plasma: no wallet wizard, readable tray ring, Sign in in the tray, task manager icon
- Retry from 30 s when offline at login; poll when the network comes up
- Mini widget and Snooze as quick-settings pills in the top-bar menu

* Mon Nov 16 2026 Vikas Kyatannawar <vikas.k@osmosys.co> - 0.1.4-1
- Mini widget drawn by GNOME Shell: above windows, on every workspace
- Redesigned widget; under pace is no longer shown as behind
- KDE installs no longer pull in GNOME Shell

* Wed Nov 11 2026 Vikas Kyatannawar <vikas.k@osmosys.co> - 0.1.3-1
- Show Pace in the top bar keeps the dashboard open

* Wed Nov 11 2026 Vikas Kyatannawar <vikas.k@osmosys.co> - 0.1.2-1
- App QA pass on live data: on-leave week, calendar redesign and day details, editable targets, widget, snooze switch and indicator

* Wed Nov 11 2026 Vikas Kyatannawar <vikas.k@osmosys.co> - 0.1.1-1
- Settings entry in the top-bar menu

* Wed Nov 11 2026 Vikas Kyatannawar <vikas.k@osmosys.co> - 0.1.0-1
- First release: reads hrms-api production (v7.50.0 Pace endpoints)

* Sun Nov 08 2026 Vikas Kyatannawar <vikas.k@osmosys.co> - 0.1.0~rc1-1
- Initial package
