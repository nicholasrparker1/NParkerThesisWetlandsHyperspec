import matplotlib.pyplot as plt
import contextily as ctx

lat = 43.14162849322316
lon = -77.50260349722205

fig, ax = plt.subplots(figsize=(6,6))

ax.scatter(lon, lat, color="red", s=100, zorder=3)

ax.set_xlim(lon-0.003, lon+0.003)
ax.set_ylim(lat-0.003, lat+0.003)

ctx.add_basemap(
    ax,
    crs="EPSG:4326",
    source=ctx.providers.OpenStreetMap.Mapnik
)

ax.set_title("Sample Location")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")

plt.tight_layout()
plt.show()

# THIS DOES NOT WORK AT THE MOMENT