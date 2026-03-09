import flet as ft

def get_course_card(course_title: str):
    return ft.Container(
        content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                ft.Container(height=100, bgcolor="#009787", content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER,alignment=ft.MainAxisAlignment.CENTER,controls=[
                    ft.Icon(ft.Icons.MENU_BOOK, size=70, color="white"),
                ])),
                ft.Column( controls=[
                    ft.Text(course_title, size=13, weight=ft.FontWeight.BOLD), 
                ],horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
            ],
        ),
        bgcolor="white",
        border_radius=10,
        height=150,
        width=160,
        on_click=lambda e: print(f"Clicked on {course_title} card"),
        shadow=ft.BoxShadow(blur_radius=2, color=ft.Colors.BLACK12, offset=ft.Offset(0, 2)),
    )