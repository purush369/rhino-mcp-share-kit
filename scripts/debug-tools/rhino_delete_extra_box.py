import System
import scriptcontext as sc

extra_id = System.Guid("992fda32-88b5-41ae-acf1-615df37c1274")
sc.doc.Objects.Delete(extra_id, True)
sc.doc.Views.Redraw()

print("Deleted:", extra_id)
