import asyncio

import flet as ft

from src.components.bottom_appbar import get_bottom_appbar

from src.components.cohorts_hub import build_cohorts_tab

from src.components.org import (

    build_org_hero_banner,

    build_org_bento_grid,

    build_org_courses_tab,

    build_org_members_tab,

    build_org_playlists_tab,

    build_org_info_tab,

    build_org_spaces_tab,

    build_teacher_portal,

    build_promo_view,

    build_create_form_view,

    open_org_edit_modal,

    open_org_plan_modal,

)

from src.requests.course_spaces import get_organisation_spaces
from src.requests.organisations import (

    get_my_organisation,

    get_organisation_members,

    get_organisation_courses,

    get_joined_organisations,

)

from src.requests.playlists import get_org_playlists

from src.utils.session_utils import get_session_user, set_session_value





async def organisations_view(page: ft.Page):

    """

    Orchestrates the Organization experience across all user roles:

    - Organization Owners & Admins -> Modern Executive Dashboard & Tab Suite

    - Faculty & Teachers           -> Dedicated Faculty Portal & Course Studio

    - Prospective Organizers       -> Zero-State Promo & Onboarding Wizard

    """

    app_bar = get_bottom_appbar(page)

    token = None

    owned_org_cache = None

    memberships_cache = []



    user_data = get_session_user(page)

    role = str(user_data.get("role", "STUDENT")).upper()



    from src.components.shimmer_skeletons import build_organisations_skeleton



    # ── Master Content Socket (1:1 high-fidelity skeleton screen while loading) ─

    content_socket = ft.Container(

        expand=True,

        content=build_organisations_skeleton(page),

    )



    # ── View Switchers ───────────────────────────────────────────────────────

    async def show_dashboard(org_data: dict):

        content_socket.content = await build_dashboard_view(org_data)

        page.update()



    def show_teacher_view(memberships=None):

        content_socket.content = build_teacher_portal(

            page=page,

            user_data=user_data,

            memberships=memberships or memberships_cache,

            token=token,

            on_back_to_admin=(lambda: page.run_task(show_dashboard, owned_org_cache)) if owned_org_cache else None,

        )

        page.update()



    def show_promo_view():

        content_socket.content = build_promo_view(on_create_click=show_create_form)

        page.update()



    def show_create_form():

        content_socket.content = build_create_form_view(

            page=page,

            token=token,

            on_org_created=show_dashboard,

            on_back=show_promo_view,

        )

        page.update()



    # ─────────────────────────────────────────────────────────────────────────

    # 1. ADMIN DASHBOARD VIEW

    # ─────────────────────────────────────────────────────────────────────────

    async def build_dashboard_view(org_data: dict) -> ft.Column:

        org_id = str(org_data.get("id", ""))

        org_name = org_data.get("name", "Academy Workspace")

        owner_id = str(org_data.get("owner_id", ""))

        current_uid = str(user_data.get("id", ""))

        is_admin = (owner_id == current_uid) or (role in ("TEACHER", "INSTRUCTOR", "STAFF", "ADMIN", "OWNER"))

        theme_color = org_data.get("theme_color") or ft.Colors.PRIMARY



        if not org_id:

            raise ValueError("build_dashboard_view received organization with no valid 'id'.")



        set_session_value(page, "current_org_id", org_id)



        plan_data = org_data.get("plan") or {}

        plan_name = plan_data.get("name", "Free Plan") if isinstance(plan_data, dict) else "Free Plan"

        max_members = plan_data.get("max_members") if isinstance(plan_data, dict) else None



        # Fetch collection data concurrently

        results = await asyncio.gather(

            get_organisation_members(token, org_id),

            get_organisation_courses(token, org_id),

            get_org_playlists(token, org_id),

            get_organisation_spaces(token, org_id),

            return_exceptions=True,

        )



        members = results[0] if isinstance(results[0], list) else []

        courses = results[1] if isinstance(results[1], list) else []

        playlists = results[2] if isinstance(results[2], list) else []

        spaces_res = results[3] if len(results) > 3 and isinstance(results[3], dict) else {}

        spaces_list = spaces_res.get("spaces", []) if isinstance(spaces_res, dict) else (results[3] if len(results) > 3 and isinstance(results[3], list) else [])

        categories_cache = []



        stats = {

            "members": len(members),

            "courses": len(courses),

            "playlists": len(playlists),
            "spaces": len(spaces_list),

            "staff": sum(1 for m in members if str(m.get("role", "")).upper() in ("TEACHER", "STAFF", "ADMIN", "OWNER", "INSTRUCTOR")),

            "students": sum(1 for m in members if str(m.get("role", "")).upper() == "STUDENT"),

            "public_courses": sum(1 for c in courses if str(c.get("public", "")).lower() == "true"),

            "campus_courses": sum(1 for c in courses if str(c.get("public", "")).lower() in ("organisation", "organization", "campus")),

            "plan": plan_name,

            "max_members": max_members,

        }



        active_tab = "courses"

        tab_content_container = ft.AnimatedSwitcher(

            content=ft.Container(expand=True),

            transition=ft.AnimatedSwitcherTransition.FADE,

            duration=180,

            reverse_duration=140,

            switch_in_curve=ft.AnimationCurve.EASE_OUT,

            switch_out_curve=ft.AnimationCurve.EASE_IN,

            expand=True,

        )



        def _update_stats():

            stats["members"] = len(members)

            stats["courses"] = len(courses)

            stats["playlists"] = len(playlists)

            stats["staff"] = sum(1 for m in members if str(m.get("role", "")).upper() in ("TEACHER", "STAFF", "ADMIN", "OWNER", "INSTRUCTOR"))

            stats["students"] = sum(1 for m in members if str(m.get("role", "")).upper() == "STUDENT")

            stats["public_courses"] = sum(1 for c in courses if str(c.get("public", "")).lower() == "true")

            stats["campus_courses"] = sum(1 for c in courses if str(c.get("public", "")).lower() in ("organisation", "organization", "campus"))

            _refresh_tab_headers()



        def _on_course_created(new_c):

            _update_stats()

            bento_grid_container.content = build_org_bento_grid(stats, on_tab_switch=_switch_tab)

            page.update()



        def _on_member_removed(uid, name):

            _update_stats()

            bento_grid_container.content = build_org_bento_grid(

                stats,

                on_tab_switch=_switch_tab,

                on_upgrade_click=lambda: open_org_plan_modal(page, org_data, theme_color, token, on_plan_upgraded=_on_plan_upgraded),

            )

            page.update()



        def _on_member_role_updated(uid, new_role):

            _update_stats()

            bento_grid_container.content = build_org_bento_grid(

                stats,

                on_tab_switch=_switch_tab,

                on_upgrade_click=lambda: open_org_plan_modal(page, org_data, theme_color, token, on_plan_upgraded=_on_plan_upgraded),

            )

            page.update()



        def _on_playlist_created(new_p):

            _update_stats()

            bento_grid_container.content = build_org_bento_grid(

                stats,

                on_tab_switch=_switch_tab,

                on_upgrade_click=lambda: open_org_plan_modal(page, org_data, theme_color, token, on_plan_upgraded=_on_plan_upgraded),

            )

            page.update()



        def _on_org_updated(new_org):

            org_data.update(new_org)

            hero_banner_holder.content = build_org_hero_banner(

                page=page,

                org_data=org_data,

                theme_color=org_data.get("theme_color") or theme_color,

                on_info_click=lambda _: _switch_tab("info"),

                on_teacher_portal_click=(lambda _: show_teacher_view()) if role in ("TEACHER", "INSTRUCTOR") else None,

                on_edit_click=lambda: open_org_edit_modal(page, org_data, theme_color, token, on_updated=_on_org_updated),

            )

            _render_tab_content()

            page.update()



        def _on_plan_upgraded(new_plan):

            org_data["plan"] = new_plan

            stats["plan"] = new_plan.get("name", "Standard")

            stats["max_members"] = new_plan.get("max_members")

            _update_stats()

            _on_org_updated(org_data)



        def _render_tab_content():

            if active_tab == "courses":

                tab_content_container.content = build_org_courses_tab(

                    page=page,

                    org_id=org_id,

                    courses=courses,

                    members=members,

                    categories_cache=categories_cache,

                    theme_color=theme_color,

                    token=token,

                    on_course_created=_on_course_created,

                )

            elif active_tab == "members":

                tab_content_container.content = build_org_members_tab(

                    page=page,

                    org_id=org_id,

                    org_name=org_name,

                    owner_id=owner_id,

                    members=members,

                    theme_color=theme_color,

                    token=token,

                    on_member_removed=_on_member_removed,

                    on_member_role_updated=_on_member_role_updated,

                )

            elif active_tab == "cohorts":

                tab_content_container.content = build_cohorts_tab(

                    page=page,

                    org_id=org_id,

                    org_data=org_data,

                    token=token,

                    is_admin=is_admin,

                    org_courses=courses,

                    org_members=members,

                    theme_color=theme_color,

                )

            elif active_tab == "playlists":

                tab_content_container.content = build_org_playlists_tab(

                    page=page,

                    org_id=org_id,

                    playlists=playlists,

                    theme_color=theme_color,

                    token=token,

                    on_playlist_created=_on_playlist_created,

                )

            elif active_tab == "spaces":

                tab_content_container.content = build_org_spaces_tab(

                    page=page,

                    org_id=org_id,

                    org_data=org_data,

                    token=token,

                    is_admin=is_admin,

                    org_courses=courses,

                    org_members=members,

                    theme_color=theme_color,

                    on_refresh_parent=_refresh_spaces_count,

                )

            elif active_tab == "info":

                tab_content_container.content = build_org_info_tab(

                    page=page,

                    org_data=org_data,

                    theme_color=theme_color,

                    token=token,

                    on_org_updated=_on_org_updated,

                    on_plan_upgraded=_on_plan_upgraded,

                )



        def _tab_button(label: str, key: str, icon_name, count: int = None):

            is_sel = (active_tab == key)

            count_tag = f" ({count})" if count is not None else ""

            return ft.Container(

                padding=ft.Padding.symmetric(horizontal=14, vertical=8),

                border_radius=10,

                bgcolor=theme_color if is_sel else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),

                animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),

                animate_scale=ft.Animation(120, ft.AnimationCurve.EASE_OUT_BACK),

                scale=1.0,

                ink=True,

                on_click=lambda _: _switch_tab(key),

                content=ft.Row(

                    spacing=6,

                    tight=True,

                    controls=[

                        ft.Icon(icon_name, size=15, color=ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE),

                        ft.Text(

                            f"{label}{count_tag}",

                            size=12,

                            weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.W_500,

                            color=ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE,

                        ),

                    ],

                ),

            )



        tab_buttons_row = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=8)



        def _refresh_spaces_count():

            async def _do_ref():

                try:

                    sp_res = await get_organisation_spaces(token, org_id)

                    nonlocal spaces_list

                    spaces_list = sp_res.get("spaces", []) if isinstance(sp_res, dict) else []

                    stats["spaces"] = len(spaces_list)

                    _refresh_tab_headers()

                    page.update()

                except Exception:

                    pass

            page.run_task(_do_ref)



        def _refresh_tab_headers():

            tab_buttons_row.controls = [

                _tab_button("Courses", "courses", ft.Icons.AUTO_STORIES_ROUNDED, len(courses)),

                _tab_button("Course Spaces", "spaces", ft.Icons.CLASS_OUTLINED, len(spaces_list)),

                _tab_button("Members", "members", ft.Icons.GROUPS_ROUNDED, len(members)),

                _tab_button("Cohorts & Exams", "cohorts", ft.Icons.SCHOOL_ROUNDED),

                _tab_button("Learning Paths", "playlists", ft.Icons.PLAYLIST_PLAY_ROUNDED, len(playlists)),

                _tab_button("Organization Details", "info", ft.Icons.INFO_OUTLINE_ROUNDED),

            ]



        def _switch_tab(tab_key: str):

            nonlocal active_tab

            active_tab = tab_key

            _refresh_tab_headers()

            _render_tab_content()

            page.update()



        # Cache active organization on page for creation studios and builders
        page._current_active_org = org_data
        page._active_auth_token = token

        _refresh_tab_headers()

        _render_tab_content()

        # Subscription Alert Banner for Grace Period / Expiration
        lifecycle_banner = ft.Container()
        sub_status = org_data.get("subscription_status")
        days_rem = org_data.get("days_remaining", 0)
        if sub_status == "grace_period":
            lifecycle_banner = ft.Container(
                margin=ft.Padding.symmetric(horizontal=16),
                padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.AMBER_600)),
                content=ft.Row([
                    ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.AMBER_700, size=20),
                    ft.Column([
                        ft.Text("Academy Subscription in Grace Period", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_900),
                        ft.Text(f"Your plan has expired. You have {days_rem} days of grace remaining before advanced features pause.", size=11.5, color=ft.Colors.AMBER_800),
                    ], spacing=2, expand=True),
                    ft.FilledButton(
                        "Renew Plan",
                        style=ft.ButtonStyle(bgcolor=ft.Colors.AMBER_700, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda _: open_org_plan_modal(page, org_data, theme_color, token, on_plan_upgraded=_on_plan_upgraded),
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )
        elif sub_status == "expired":
            lifecycle_banner = ft.Container(
                margin=ft.Padding.symmetric(horizontal=16),
                padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.RED_600),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.RED_600)),
                content=ft.Row([
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=ft.Colors.RED_600, size=20),
                    ft.Column([
                        ft.Text("Academy Subscription Expired", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_700),
                        ft.Text("Advanced features are paused. All existing student grades, courses, and lessons are safe.", size=11.5, color=ft.Colors.RED_600),
                    ], spacing=2, expand=True),
                    ft.FilledButton(
                        "Renew Plan Now",
                        style=ft.ButtonStyle(bgcolor=ft.Colors.RED_600, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda _: open_org_plan_modal(page, org_data, theme_color, token, on_plan_upgraded=_on_plan_upgraded),
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )

        hero_banner_holder = ft.Container(

            content=build_org_hero_banner(

                page=page,

                org_data=org_data,

                theme_color=theme_color,

                on_info_click=lambda _: _switch_tab("info"),

                on_teacher_portal_click=(lambda _: show_teacher_view()) if role in ("TEACHER", "INSTRUCTOR") else None,

                on_edit_click=lambda: open_org_edit_modal(page, org_data, theme_color, token, on_updated=_on_org_updated),

            )

        )



        bento_grid_container = ft.Container(

            content=build_org_bento_grid(

                stats,

                on_tab_switch=_switch_tab,

                on_upgrade_click=lambda: open_org_plan_modal(page, org_data, theme_color, token, on_plan_upgraded=_on_plan_upgraded),

            )

        )



        return ft.Column(

            expand=True,

            scroll=ft.ScrollMode.AUTO,

            spacing=10,

            controls=[

                hero_banner_holder,

                lifecycle_banner,

                ft.Container(

                    padding=ft.Padding.symmetric(horizontal=16),

                    content=ft.Column(

                        spacing=12,

                        controls=[

                            bento_grid_container,

                            tab_buttons_row,

                            ft.Container(

                                padding=16,

                                border_radius=16,

                                bgcolor=ft.Colors.SURFACE,

                                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),

                                content=tab_content_container,

                            ),

                            ft.Container(height=24),

                        ],

                    ),

                ),

            ],

        )



    # ─────────────────────────────────────────────────────────────────────────

    # 2. STATUS RESOLVER (Safe against truthy error dicts & role bypasses)

    # ─────────────────────────────────────────────────────────────────────────

    async def fetch_org_status():

        nonlocal token, owned_org_cache, memberships_cache

        token = await page.shared_preferences.get("auth_token")



        try:

            # 1. Attempt to fetch owned organization

            org_data = await asyncio.wait_for(get_my_organisation(token), timeout=15)

            is_valid_org = (

                isinstance(org_data, dict)

                and bool(org_data.get("id"))

                and not bool(org_data.get("error"))

            )



            if is_valid_org:

                owned_org_cache = org_data

                await show_dashboard(org_data)

                return



            # 2. If not an org owner, check if user is faculty or member of joined orgs

            try:

                joined = await asyncio.wait_for(get_joined_organisations(token), timeout=10)

                memberships_cache = joined if isinstance(joined, list) else []

            except Exception:

                memberships_cache = []



            if role in ("TEACHER", "INSTRUCTOR") or bool(memberships_cache):

                show_teacher_view(memberships_cache)

            else:

                show_promo_view()



        except asyncio.TimeoutError:

            content_socket.content = ft.Container(

                expand=True,

                alignment=ft.Alignment.CENTER,

                padding=30,

                content=ft.Column(

                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,

                    alignment=ft.MainAxisAlignment.CENTER,

                    spacing=10,

                    controls=[

                        ft.Icon(ft.Icons.WIFI_OFF_ROUNDED, size=48, color=ft.Colors.ORANGE_400),

                        ft.Text("Connection timed out", size=17, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),

                        ft.Text(

                            "Please check your internet connection and try again.",

                            size=13,

                            color=ft.Colors.ON_SURFACE_VARIANT,

                            text_align=ft.TextAlign.CENTER,

                        ),

                        ft.Container(height=8),

                        ft.FilledButton(

                            "Retry",

                            style=ft.ButtonStyle(

                                bgcolor=ft.Colors.PRIMARY,

                                shape=ft.RoundedRectangleBorder(radius=10),

                            ),

                            on_click=lambda _: page.run_task(fetch_org_status),

                        ),

                    ],

                ),

            )

            page.update()



        except Exception as ex:

            content_socket.content = ft.Container(

                expand=True,

                alignment=ft.Alignment.CENTER,

                padding=30,

                content=ft.Column(

                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,

                    alignment=ft.MainAxisAlignment.CENTER,

                    spacing=10,

                    controls=[

                        ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=48, color=ft.Colors.RED_400),

                        ft.Text("Something went wrong", size=17, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),

                        ft.Text(

                            f"{type(ex).__name__}: unable to load academy workspace.",

                            size=13,

                            color=ft.Colors.ON_SURFACE_VARIANT,

                            text_align=ft.TextAlign.CENTER,

                        ),

                        ft.Container(height=8),

                        ft.FilledButton(

                            "Retry",

                            style=ft.ButtonStyle(

                                bgcolor=ft.Colors.PRIMARY,

                                shape=ft.RoundedRectangleBorder(radius=10),

                            ),

                            on_click=lambda _: page.run_task(fetch_org_status),

                        ),

                    ],

                ),

            )

            page.update()



    # ── await background fetch so view is feasibly ready on transition ─────────

    try:

        await asyncio.wait_for(fetch_org_status(), timeout=8.0)

    except Exception as _oex:

        print(f"[organisations_view] Initial fetch error or timeout: {_oex}")



    return ft.View(

        route="/organisations",

        bottom_appbar=app_bar,

        bgcolor=ft.Colors.SURFACE_CONTAINER,

        padding=0,

        controls=[

            ft.SafeArea(expand=True, content=content_socket)

        ],

    )

