import flet as ft

def test():
    # Test 1: TextField(expand=True) in Row(wrap=True)
    tb = ft.TextField(expand=True)
    r = ft.Row([tb], wrap=True)
    
    # Test 2: Container(expand=True) inside Column inside Scroll Column
    c1 = ft.Container(expand=True)
    c2 = ft.Container(content=c1)
    col = ft.Column([c2], scroll=ft.ScrollMode.AUTO)
    print("Objects created successfully")

test()
