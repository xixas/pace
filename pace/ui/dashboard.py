"""The dashboard window content: Week (C1, C2, C5, A8, A13), Month (C3) and Calendar (C4) behind one header (mock C1)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
from gi.repository import Adw, GLib, GObject, Gtk, Pango  # noqa: E402

from pace.ui import config, model, period  # noqa: E402
from pace.ui.draw import Sparkline, SplitBar, WeekBar  # noqa: E402
from pace.ui.widgets import action_row, box, clear, label, open_uri, pill, run_async  # noqa: E402

PINESTEM = "https://pinestem.com/dashboard.html#/tasks"
NARROW = 560  # below this (in sp) the view switcher moves from the header to a bottom bar


def status_page(
    icon: str, title: str, body: str = "", pill_text: str | None = None, button: tuple | None = None
) -> Adw.StatusPage:
    page = Adw.StatusPage(icon_name=icon, title=title, description=body, vexpand=True)
    holder = box(spacing=18, halign=Gtk.Align.CENTER)
    if pill_text:
        holder.append(pill(pill_text, "grey", halign=Gtk.Align.CENTER))
    if button:
        b = Gtk.Button(label=button[0], halign=Gtk.Align.CENTER, css_classes=["pill", "suggested-action"])
        b.connect("clicked", lambda *_: button[1]())
        holder.append(b)
    if pill_text or button:
        page.set_child(holder)
    return page


def stat(title: str, value: str, sub: str = "", badge: Gtk.Widget | None = None) -> Gtk.Box:
    """A small labelled number: caption, value, one dim line (optionally with a pill in front)."""
    col = box(label(title, "caption", "dim-label"), label(value, "pace-value", "numeric"), spacing=2)
    if badge or sub:
        row = box(vertical=False, spacing=8)
        if badge:
            row.append(badge)
        if sub:
            row.append(label(sub, "caption", "dim-label", wrap=True, valign=Gtk.Align.CENTER))
        col.append(row)
    return col


def icon_row(icon: str, title: str, subtitle: str, colour_class: str) -> Adw.PreferencesGroup:
    """One-row group with a coloured symbolic icon in front: the C2 short-days warning and the A11 note."""
    row = action_row(title, subtitle)
    row.add_prefix(Gtk.Image(icon_name=icon, css_classes=[colour_class], pixel_size=20))
    group = Adw.PreferencesGroup()
    group.add(row)
    return group


class Dashboard(Adw.BreakpointBin):
    def __init__(self, services, window, now=datetime.now):
        super().__init__(width_request=360, height_request=300)
        self.services, self.window, self.now = services, window, now
        self.status: dict = {}
        self.month_first = now().date().replace(day=1)
        self.rows: list[dict] | None = None
        self.rows_error: str | None = None
        self.week_rows: list[dict] = []
        self.ahead_rows: list[dict] = []
        self._banner_kind = None
        self._dismissed: set[str] = set()
        self._week_gen = self._month_gen = 0

        self.toolbar = Adw.ToolbarView()
        self.set_child(self.toolbar)
        self.ago = label("", "dim-label", "caption")
        self.refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Refresh now")
        self.refresh_btn.connect("clicked", self._on_refresh)
        header = Adw.HeaderBar()
        header.pack_start(box(self.refresh_btn, self.ago, vertical=False, spacing=6, valign=Gtk.Align.CENTER))
        self.stack = Adw.ViewStack()
        self.week_body, self.month_body, self.cal_body = (box(spacing=18) for _ in range(3))
        for name, title, icon, body in (
            ("week", "Week", "view-list-symbolic", self.week_body),
            ("month", "Month", "x-office-calendar-symbolic", self.month_body),
            ("calendar", "Calendar", "view-grid-symbolic", self.cal_body),
        ):
            self.stack.add_titled_with_icon(self._scroller(body), name, title, icon)
        switcher = Adw.ViewSwitcher(stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        header.set_title_widget(switcher)
        menu = Gtk.MenuButton(
            icon_name="open-menu-symbolic", menu_model=window.build_menu(), primary=True, tooltip_text="Main menu"
        )
        header.pack_end(menu)
        self.toolbar.add_top_bar(header)
        self.skew_banner = Adw.Banner(revealed=False, use_markup=False)
        self.skew_banner.connect("button-clicked", lambda *_: window.skew_action())
        self.banner = Adw.Banner(revealed=False, use_markup=False)
        self.banner.connect("button-clicked", self._on_banner)
        self.toolbar.add_top_bar(self.skew_banner)
        self.toolbar.add_top_bar(self.banner)
        self.toolbar.set_content(self.stack)
        switcher_bar = Adw.ViewSwitcherBar(stack=self.stack)
        self.toolbar.add_bottom_bar(switcher_bar)
        narrow = Adw.Breakpoint.new(Adw.BreakpointCondition.parse(f"max-width: {NARROW}sp"))
        narrow.add_setter(switcher_bar, "reveal", True)
        narrow.add_setter(header, "title-widget", GObject.Value(Gtk.Widget, None))
        self.add_breakpoint(narrow)
        self.stack.connect("notify::visible-child-name", lambda *_: self._ensure_month())
        GLib.timeout_add_seconds(20, self._tick)

    @staticmethod
    def _scroller(body: Gtk.Box) -> Gtk.ScrolledWindow:
        clamp = Adw.Clamp(
            maximum_size=760,
            tightening_threshold=560,
            child=body,
            margin_top=18,
            margin_bottom=30,
            margin_start=16,
            margin_end=16,
        )
        return Gtk.ScrolledWindow(child=clamp, hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)

    # ---- updates -------------------------------------------------------------------------------------------------

    def set_status(self, status: dict) -> None:
        self.status = status
        self._tick()
        self._render_banners()
        self.render_week()
        self._load_week_rows()
        if self.rows is not None:
            self.render_month()
            self.render_calendar()

    def _tick(self) -> bool:
        now = self.now()
        if self.status.get("state") == "signed_out" or model.is_stale(self.status, now):
            as_of = model.parse_dt(self.status.get("as_of"))
            self.ago.set_label(f"as of {as_of:%H:%M}" if as_of else "never")
        else:
            self.ago.set_label(model.as_of_text(self.status, now))
        return True

    def _expected_h(self) -> float:
        return config.load_settings()["expected_daily_h"]

    def _is_stale(self) -> bool:
        return self.status.get("state") == "signed_out" or model.is_stale(self.status, self.now())

    def _render_banners(self) -> None:
        kind = model.skew(self.status)
        self.skew_banner.set_revealed(bool(kind))
        if kind == "service_old":
            self.skew_banner.set_title("Log out and back in to load the new panel extension")
            self.skew_banner.set_button_label("Log out now")
        elif kind == "app_old":
            self.skew_banner.set_title("Pace was updated. Close and reopen it to load the new version")
            self.skew_banner.set_button_label("Quit")
        b = model.banner(self.status)
        if b and b["kind"] in self._dismissed:
            b = None
        self._banner_kind = b["kind"] if b else None
        self._banner = b
        self.banner.set_revealed(bool(b))
        if b:
            self.banner.set_title(b["text"])
            self.banner.set_button_label(b["button"] or "")

    def _on_banner(self, *_):
        kind = self._banner_kind
        if kind == "signed_out":
            self.window.sign_in_again()
        elif kind == "no_mapping":
            self._dismissed.add(kind)
            self._render_banners()
        elif kind == "last_week":
            open_uri(self, self._banner.get("url") or PINESTEM)

    def _on_refresh(self, *_):
        self.refresh_btn.set_sensitive(False)

        def done(ok):
            self.refresh_btn.set_sensitive(True)
            if not ok:
                self.window.toast("Pace isn't running")

        self.services.refresh(done)

    # ---- week ----------------------------------------------------------------------------------------------------

    def _load_week_rows(self) -> None:
        if not self.services.has_history():
            return
        today = self.now().date()
        monday, sunday = model.week_bounds(today)
        want_ahead = self.status.get("state") == "no_mapping" or (self.status.get("problem") or {}).get("kind") == "no_mapping"
        start = today.replace(day=1) if want_ahead else monday
        end = today + timedelta(days=60) if want_ahead else sunday
        gen = self._week_gen = self._week_gen + 1

        def done(rows, error):
            if error or gen != self._week_gen:
                return
            self.week_rows, self.ahead_rows = rows, (rows if want_ahead else [])
            self.render_week()

        run_async(lambda: self.services.history(start, end), done)

    def render_week(self) -> None:
        clear(self.week_body)
        s = self.status
        stale = self._is_stale()
        (self.week_body.add_css_class if stale else self.week_body.remove_css_class)("pace-stale")
        if s.get("state") == "no_mapping" or (s.get("problem") or {}).get("kind") == "no_mapping":
            return self._render_no_mapping()
        if empty := model.empty_state(s):
            button = (empty["button"], lambda: open_uri(self, s.get("pinestem_url") or PINESTEM)) if empty.get("button") else None
            self.week_body.append(status_page(empty["icon"], empty["title"], empty["body"], empty.get("pill"), button))
            return
        view = model.week_view(s, self._expected_h(), model.week_split(self.week_rows), stale=stale)
        if view is None:
            msg = (s.get("problem") or {}).get("message") or "Waiting for the first numbers from Pace."
            self.week_body.append(status_page("preferences-system-time-symbolic", "No numbers yet", msg))
            return
        if stale and (as_of := model.parse_dt(s.get("as_of"))):
            head = view["stats"][0]
            head["label"] = f"Week · {s.get('title') or 'This week'} as of {as_of:%H:%M}"
        self.week_body.append(self._hero(view))
        if view["warning"]:
            self.week_body.append(icon_row("dialog-warning-symbolic", view["warning"], view["warning_detail"] or "", "warning"))
        codes = self._series_codes(view["cards"])
        days = Gtk.FlowBox(
            homogeneous=True,
            min_children_per_line=3,
            max_children_per_line=5,
            row_spacing=10,
            column_spacing=10,
            selection_mode=Gtk.SelectionMode.NONE,
            css_classes=["pace-days"],
        )
        for c in view["cards"]:
            days.append(self._day(c, codes))
        self.week_body.append(days)
        if projects := (s.get("month") or {}).get("projects"):
            self.week_body.append(self._month_group(s["month"], projects))

    def _hero(self, view: dict) -> Gtk.Box:
        """C1 top card: the week's hours as the one big number, the verdict pill and advice, the bar, then the small stats."""
        head, *rest = view["stats"]
        top = box(label(head["label"], "caption-heading", "dim-label"), spacing=6)
        top.append(label(head["value"], "pace-hero"))
        verdict = box(vertical=False, spacing=10, margin_top=4)
        if head["badge"]:
            verdict.append(pill(head["badge"], view["colour"]))
        if head["sub"]:
            verdict.append(label(head["sub"], "body", wrap=True, valign=Gtk.Align.CENTER))
        top.append(verdict)
        bar = WeekBar()
        bar.set_data(view["bar"], view["colour"])
        progress = box(
            box(
                label(view["week_label"], "caption-heading", "dim-label", hexpand=True),
                label(view["bar_text"], "caption-heading", "numeric"),
                vertical=False,
            ),
            bar,
            spacing=6,
            margin_top=18,
        )
        stats = Adw.WrapBox(child_spacing=32, line_spacing=14, margin_top=16, justify=Adw.JustifyMode.NONE)
        for st in rest:
            stats.append(stat(st["label"], st["value"], st["sub"]))
        return box(top, progress, Gtk.Separator(margin_top=18), stats, classes=("card", "pace-hero-card"))

    @staticmethod
    def _series_codes(cards: list[dict]) -> list[str]:
        """Project codes in the order they get their colour: biggest week total first."""
        totals: dict[str, float] = {}
        for c in cards:
            for code, h in c["split"]:
                totals[code] = totals.get(code, 0) + float(h)
        return sorted(totals, key=lambda c: -totals[c])

    def _day(self, c: dict, codes: list[str]) -> Gtk.Button:
        inner = box(spacing=3)
        dow = label(c["dow"], "caption-heading", "dim-label", xalign=0.5)
        if c["today"]:
            dow = label(c["dow"] + " · today", "caption-heading", "accent", xalign=0.5)
        inner.append(dow)
        inner.append(label(c["text"], "pace-day-text", xalign=0.5))
        if c["split"]:
            total = sum(float(h) for _, h in c["split"]) or 1
            strip = SplitBar()
            strip.set_data([(float(h) / total, codes.index(code)) for code, h in c["split"]])
            strip.set_margin_top(4)
            strip.set_margin_bottom(4)
            strip.set_margin_start(10)
            strip.set_margin_end(10)
            inner.append(strip)
        for code, h in c["split"]:
            inner.append(label(f"{code} {h}", "caption", "dim-label", "numeric", xalign=0.5))
        if c["foot"]:
            inner.append(label(c["foot"], "caption", "dim-label", xalign=0.5, margin_top=2))
        btn = Gtk.Button(child=inner, css_classes=["card", "pace-day", c["kind"]] + (["today"] if c["today"] else []))
        btn.set_tooltip_text("Open PineStem")
        btn.connect("clicked", lambda *_: open_uri(self, self.status.get("pinestem_url") or PINESTEM))
        return btn

    def _month_group(self, month: dict, projects: list[dict]) -> Adw.PreferencesGroup:
        """The month's project targets under the week, one row each; activating a row opens the Month tab."""
        left = month.get("working_days_left")
        group = Adw.PreferencesGroup(
            title=f"{month.get('name') or 'This month'} by project",
            description=f"{left} working day{'s' if left != 1 else ''} left" if left is not None else None,
        )
        for p in projects:
            text, colour = period.project_badge(p)
            sub = " · ".join(x for x in (p.get("text"), p.get("need_text")) if x)
            row = action_row(p["name"], sub, activatable=True)
            row.add_suffix(pill(text, colour))
            row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
            row.connect("activated", lambda *_: self.stack.set_visible_child_name("month"))
            group.add(row)
        return group

    def _render_no_mapping(self) -> None:
        cards = (
            period.no_mapping_cards(self.ahead_rows, self.now().date())
            if self.ahead_rows
            else [("This week", "—", "no billing data")]
        )
        tiles = Adw.WrapBox(child_spacing=40, line_spacing=18, justify=Adw.JustifyMode.NONE)
        for t, v, sub in cards:
            tiles.append(stat(t, v, sub))
        self.week_body.append(box(tiles, classes=("card", "pace-hero-card")))

    # ---- month and calendar ----------------------------------------------------------------------------------------

    def _ensure_month(self) -> None:
        if self.stack.get_visible_child_name() in ("month", "calendar") and self.rows is None and self.rows_error is None:
            self.load_month()

    def load_month(self) -> None:
        first, last = period.month_bounds(self.month_first)
        self.rows, self.rows_error = None, None
        self._render_loading()
        gen = self._month_gen = self._month_gen + 1

        def done(rows, error):
            if gen != self._month_gen:
                return
            self.rows = rows if not error else None
            self.rows_error = None if not error else self._history_error(error)
            self.render_month()
            self.render_calendar()

        if not self.services.has_history():
            self.rows_error = "History isn't available yet in this build."
            return self._after_error()
        run_async(lambda: self.services.history(first, last), done)

    def _after_error(self):
        self.render_month()
        self.render_calendar()

    @staticmethod
    def _history_error(error: BaseException) -> str:
        from pace.client import Offline, SignedOut

        if isinstance(error, Offline):
            return "Can't reach DhiHRMS. Month and calendar need a connection."
        if isinstance(error, SignedOut):
            return "Your sign-in expired. Sign in again to load the month."
        return f"Couldn't load the month: {error}"

    def _render_loading(self) -> None:
        for body in (self.month_body, self.cal_body):
            clear(body)
            body.append(Adw.Spinner(halign=Gtk.Align.CENTER, margin_top=60, width_request=32, height_request=32))

    def _nav(self) -> Gtk.Box:
        prev = Gtk.Button(icon_name="go-previous-symbolic", css_classes=["flat", "circular"], tooltip_text="Previous month")
        nxt = Gtk.Button(icon_name="go-next-symbolic", css_classes=["flat", "circular"], tooltip_text="Next month")
        prev.connect("clicked", lambda *_: self._go(-1))
        nxt.connect("clicked", lambda *_: self._go(1))
        title = label(f"{self.month_first:%B %Y}", "title-2", xalign=0.5, hexpand=True)
        return box(prev, title, nxt, vertical=False, spacing=6)

    def _go(self, delta: int) -> None:
        self.month_first = period.shift_month(self.month_first, delta)
        self.load_month()

    def _problem(self, body: Gtk.Box) -> bool:
        if self.rows is None:
            clear(body)
            body.append(self._nav())
            body.append(status_page("network-offline-symbolic", "Nothing to show", self.rows_error or ""))
            return True
        return False

    def render_month(self) -> None:
        body = self.month_body
        if self.rows is None and self.rows_error is None:
            return
        if self._problem(body):
            return
        clear(body)
        body.append(self._nav())
        targets, today = config.load_targets(), self.now().date()
        for p in period.month_projects(self.rows, targets, self.month_first, self.status, today):
            body.append(self._project_card(p, targets, today))
        table = period.week_table(self.rows, self.month_first)
        body.append(self._table(table))
        if note := period.footnote(self.rows):
            body.append(
                label(
                    f"*Total includes non-billable (used for pay). Targets use billable only. {note}",
                    "caption",
                    "dim-label",
                    wrap=True,
                    margin_start=4,
                )
            )

    def _project_card(self, p: dict, targets: dict, today: date) -> Gtk.Box:
        text, colour = period.project_badge(p)
        head = box(
            label(p["name"], "heading"),
            label(p["code"], "caption", "dim-label", hexpand=True),
            pill(text, colour),
            vertical=False,
            spacing=8,
        )
        card = box(head, classes=("card", "pace-hero-card"), spacing=4)
        if not p.get("target_min"):
            card.append(label(f"{model.hours(p['billed_min'])} h", "title-1", "numeric", margin_top=6))
            card.append(label("tracked only · billable", "caption", "dim-label"))
            return card
        card.append(
            box(
                label(f"{model.hours(p['billed_min'])} / {model.h_short(p['target_min'])} h", "title-1", "numeric", hexpand=True),
                label(
                    period.target_note(targets, p["code"]),
                    "caption",
                    "dim-label",
                    valign=Gtk.Align.END,
                    xalign=1,
                    wrap=True,
                    justify=Gtk.Justification.RIGHT,
                ),
                vertical=False,
                margin_top=6,
            )
        )
        series = [(d, v) for d, v in period.cumulative(self.rows, p["code"]) if d <= today]
        expected = period.expected_line(self.rows, p["target_min"])
        spark = Sparkline()
        spark.set_margin_top(10)
        spark.set_data(
            [v for _, v in series],
            [v for _, v in expected],
            max(p["target_min"], p["billed_min"]),
            colour,
            *period.axis_labels(p["target_min"], self.rows),
        )
        by_now = next((v for d, v in reversed(expected) if d <= today), 0)
        facts = " · ".join(x for x in (p.get("need_text"), f"expected by now {model.hours(by_now)} h") if x)
        card.append(label(facts, "caption", "dim-label", wrap=True))
        card.append(spark)
        working = sum(r["working"] for r in self.rows) or 1
        card.append(
            box(
                label(
                    f"expected: {model.h_short(p['target_min'] / working)} h per working day",
                    "caption",
                    "dim-label",
                    hexpand=True,
                ),
                label(f"actual {model.hours(p['billed_min'])} h", "caption", "dim-label"),
                vertical=False,
                margin_top=4,
            )
        )
        return card

    def _table(self, t: dict) -> Gtk.Box:
        cols = ["Week", "Days", *t["codes"], "Total*"]
        sizes = [Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL) for _ in cols]

        def row(cells, classes=()):
            r = box(vertical=False, spacing=14, classes=classes)
            for i, text in enumerate(cells):
                lab = label(text, xalign=0 if i == 0 else 1, hexpand=i == 0)
                if i:
                    lab.add_css_class("numeric")
                sizes[i].add_widget(lab)
                r.append(lab)
            return r

        card = box(classes=("card", "pace-table"))
        card.append(label(f"{self.month_first:%B}, week by week", "heading", "pace-table-title"))
        card.append(row(cols, ("pace-table-head",)))
        monday = model.week_bounds(self.now().date())[0].isoformat()
        for w in t["weeks"]:
            cells = [
                w["label"],
                f"{w['days']:g}",
                *(model.hours(w["by_code"].get(c, 0)) for c in t["codes"]),
                model.hours(w["total_min"]),
            ]
            r = row(cells, ("pace-table-row",))
            if w["monday"] == monday:
                r.add_css_class("accent")
                btn = Gtk.Button(child=r, css_classes=["flat", "pace-table-btn"], tooltip_text="Show this week")
                btn.connect("clicked", lambda *_: self.stack.set_visible_child_name("week"))
                card.append(btn)
            else:
                card.append(r)
        tot = t["total"]
        card.append(
            row(
                [
                    "Month",
                    f"{tot['days']:g}",
                    *(model.hours(tot["by_code"][c]) for c in t["codes"]),
                    model.hours(tot["total_min"]),
                ],
                ("pace-table-total",),
            )
        )
        return card

    def render_calendar(self) -> None:
        body = self.cal_body
        if self.rows is None and self.rows_error is None:
            return
        if self._problem(body):
            return
        clear(body)
        body.append(self._nav())
        floor = config.load_targets()["dailyMinimum"]
        grid = Gtk.Grid(row_spacing=6, column_spacing=6, column_homogeneous=True)
        for i, dow in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            grid.attach(label(dow, "caption-heading", "dim-label", xalign=0.5, margin_bottom=4), i, 0, 1, 1)
        for r, week in enumerate(period.calendar_grid(self.rows, self.month_first, self.now().date(), floor), start=1):
            for c, cell in enumerate(week):
                grid.attach(self._cell(cell), c, r, 1, 1)
        body.append(grid)
        low = floor - 1.5
        legend = Adw.WrapBox(
            child_spacing=16, line_spacing=8, justify=Adw.JustifyMode.NONE, halign=Gtk.Align.CENTER, margin_top=4
        )
        for cls, text in (
            ("heat-ok", f"≥ {floor:g} h"),
            ("heat-mid", f"{low:g}–{floor - 0.1:.1f} h"),
            ("heat-low", f"< {low:g} h"),
            ("heat-pending", "not billed yet"),
            ("heat-holiday", "holiday"),
            ("heat-leave", "leave"),
        ):
            sw = Gtk.Box(css_classes=["swatch", cls], valign=Gtk.Align.CENTER)
            legend.append(box(sw, label(text, "caption", "dim-label"), vertical=False, spacing=6))
        body.append(legend)
        body.append(
            label(
                f"Colour = total billed hours that day vs the {floor:g} h daily minimum. Weekends are never counted.",
                "caption",
                "dim-label",
                wrap=True,
                xalign=0.5,
                justify=Gtk.Justification.CENTER,
            )
        )

    def _cell(self, cell: dict) -> Gtk.Widget:
        if cell["day"] is None:
            return Gtk.Box(css_classes=["heat-cell"])
        value = label(cell["label"], "heat-val", ellipsize=Pango.EllipsizeMode.END, max_width_chars=3)
        inner = box(label(str(cell["day"]), "heat-day"), value, spacing=2, valign=Gtk.Align.START)
        btn = Gtk.Button(child=inner, css_classes=["flat", "heat-cell", cell["cls"]] + (["today"] if cell["today"] else []))
        if cell["tip"]:
            btn.set_tooltip_text(cell["tip"])
        if cell["cls"] != "heat-off":
            btn.connect("clicked", lambda *_: open_uri(self, self.status.get("pinestem_url") or PINESTEM))
        return btn
