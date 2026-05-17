import rhinoscriptsyntax as rs
import scriptcontext as sc

corners = [
    (0, 0, 0),
    (10, 0, 0),
    (10, 10, 0),
    (0, 10, 0),
    (0, 0, 10),
    (10, 0, 10),
    (10, 10, 10),
    (0, 10, 10),
]

box_id = rs.AddBox(corners)
sc.doc.Views.Redraw()

print("Created box:", box_id)
