import xarray as xr
import matplotlib.pyplot as plt

FILE = "./TEJapan_15S_FloodData/TE-JPN01M_MSM_H2025071504_FLDDPH.nc"  # adjust path if needed

# 1) open the NetCDF file lazily (reads metadata only)
ds = xr.open_dataset(FILE)

# 2) quick overview of dimensions, coordinates & variables
print(ds)                          # same as `ncdump -h`

# 3) inspect one variable’s metadata
print(ds.FLDDPH)                   # dtype, dims, units, attrs

# 4) peek at values (⚠ could be large!  use .isel to subset)
first_slice = ds.FLDDPH.isel(time=0)  # first time step
print(first_slice.values)             # 2-D NumPy array

# 5) plot (basic preview – tweak cmap, figsize, etc. as you like)
first_slice.plot()
plt.title("FLDDPH at t=0")        # depth/precip/etc. depending on units
plt.tight_layout()
plt.show()

# 6) clean up file handle
ds.close()