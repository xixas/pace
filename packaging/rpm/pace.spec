Name:           pace
Version:        0.1.1
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
Recommends:     gnome-shell-extension-common

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
%{_datadir}/applications/io.github.xixas.Pace.desktop
%{_datadir}/applications/io.github.xixas.Pace.widget.desktop
%config(noreplace) %{_sysconfdir}/xdg/autostart/io.github.xixas.Pace.daemon.desktop
%{_datadir}/icons/hicolor/scalable/apps/io.github.xixas.Pace.svg
%{_datadir}/icons/hicolor/symbolic/apps/io.github.xixas.Pace-symbolic.svg
%{_datadir}/metainfo/io.github.xixas.Pace.metainfo.xml

%changelog
* Wed Nov 11 2026 Vikas Kyatannawar <vikas.k@osmosys.co> - 0.1.1-1
- Settings entry in the top-bar menu

* Wed Nov 11 2026 Vikas Kyatannawar <vikas.k@osmosys.co> - 0.1.0-1
- First release: reads hrms-api production (v7.50.0 Pace endpoints)

* Sun Nov 08 2026 Vikas Kyatannawar <vikas.k@osmosys.co> - 0.1.0~rc1-1
- Initial package
