import pandas as pd
import xarray as xr
import numpy as np
from src.cal_parsing.julian_arithmetics import JulianDate
from src.cal_parsing.julian_arithmetics import JulianCalendarParse
from time import perf_counter
from src.lib.QNC_defintions import Output_Time_Res
from src.lib.QNC_defintions import Second_dim_type
from enum import Enum




class QNC_ncdf_reader:
    def __init__(self, output_path, output_cats, output_identifier, output_time_res):

        self.output_path = output_path
        self.output_time_res = output_time_res
        self.output_identifier = output_identifier
        self.output_cat_names = output_cats

        self.soil_depths = []
        self.Second_dim =  Second_dim_type.Invalid



    def parse_env_and_variables(self, pandas_time = False):
        self.files = {}
        for name in self.output_cat_names:
            self.files[name] = xr.open_dataset(
                self.output_path + '/' + name + '_'+   self.output_identifier + "_"  +  str(self.output_time_res.name).lower() +'.nc'
                , decode_times=False)

        print(f"     Reading time variable... ", end='')
        t1_start = perf_counter()

        # Get the time variable from the first output file
        time = self.files[self.output_cat_names[0]]['time'].load().values.astype(int)

        # Accounting for a bug in the output of output module. We sometimes have one timestep too much
        if (self.output_time_res ==  Output_Time_Res.Timestep) & (time[0] > 0):
            time -= 1800


        time_units = self.files[self.output_cat_names[0]]['time'].attrs['units']
        t_stop = perf_counter()
        print(f"     Done! ({np.round(t_stop-t1_start, 1)} sec.)")

        # Parse time to calendar variable
        print(f"     Parsing time variable... ", end='')
        t1_start = perf_counter()
        jcp = JulianCalendarParse()
        jcp.GetStartDateFromNetCDFUnitString(time_units)


        # Parse time and create main data frame object
        # Using C version of calendar parsing
        self.dF = jcp.ParseDatesC(time)

        #  Diagnostic to check whether this is still from old ouptut files
        if self.dF['year'].iloc[0] == 0:
            self.dF['year'] += 1900





        self.dF['date'] = self.dF['year'].map(str) + "-" + self.dF['month'].map(self._int2strZ) + '-' + self.dF[
                'day'].map(
                self._int2strZ) + ' ' + self.dF['hour'].map(self._int2strZ) + ':' + self.dF['min'].map(
                self._int2strZ) + ':' + self.dF['sec'].map(self._int2strZ)


        # If we have a timespan low enough (from ~ 1600 to 2100) we can acutally use the pandas datetime
        if pandas_time:
            self.dF['date'] = pd.to_datetime(self.dF['date'], format='%Y-%m-%d %H:%M')

        self.times_np_64 = np.empty(self.dF.shape[0], dtype='datetime64[s]')
        for i in range(0, self.dF.shape[0]):
            self.times_np_64[i] = np.datetime64(self.dF['date'][i])

        t_stop = perf_counter()
        print(f"Done! ({np.round(t_stop-t1_start, 1)} sec.)")


        print(f"     Reading variable names and units... ", end='')

        self.Dataset_Names_2D = {}
        self.Dataset_Names_1D = {}

        self.Units_2D = {}
        self.Second_dims_2D = {}
        self.Units_1D = {}

        for name in self.output_cat_names:

            df_local_2D_var_names = []
            df_local_1D_var_names = []

            dict_units_1D = {}
            dict_units_2D = {}

            vars = self.files[name].data_vars

            for var in vars:

                dim = len(self.files[name][var].shape)
                if (var != 'time') &(var != 'soil_depth')& (dim == 1):
                    df_local_1D_var_names.append(var);
                    dict_units_1D[var] = self.files[name][var].attrs['units']

                elif(var != 'time')&(var != 'soil_depth') & (dim == 2):
                    df_local_2D_var_names.append(var)
                    dict_units_2D[var] = self.files[name][var].attrs['units']

                    second_dim = vars[var].dims[1]

                    self.Second_dims_2D[var] = second_dim
                    self.Nsecond_dim = vars[var].shape[1]

                    if second_dim == "canopy_layer":
                        self.Second_dim = Second_dim_type.Canopy_layer
                    elif second_dim == "soil_layer":
                        self.Second_dim = Second_dim_type.Soil_layer
                    else:
                        "Invaild or unsuppored second dimensionf ncdf output"

                elif var == "soil_depth":
                    self.soil_depths = self.files[name][var].data




            self.Dataset_Names_1D[name] = df_local_1D_var_names
            self.Dataset_Names_2D[name] = df_local_2D_var_names

            self.Units_1D[name] = dict_units_1D
            self.Units_2D[name] = dict_units_2D

        t_stop = perf_counter()
        print(f"Done! ({np.round(t_stop - t1_start, 1)} sec.)")


    def check_1D_variables(self, target_variables):
        grp_var_target_found = []
        for grp in target_variables:
            var_target_found = []
            for var in grp:

                cat = var[0]
                name = var[1]
                keys =  self.files[cat].keys()
                if name in keys:
                    var_target_found.append(True)
                else:
                    var_target_found.append(False)
                    print(f"Could not find {var}... in {self.output_identifier}_{self.output_time_res.name.lower()}.nc'...Skipping!")
            grp_var_target_found.append(var_target_found)
        return grp_var_target_found;

    def read_1D_flat(self, cat_name, var_name):

        # Reading in all output data into dataframes.
        # This could be improved at one point...
        print(f"Reading 1D variable... ", end='')
        t1_start = perf_counter()

        arr_1d = self.files[cat_name][var_name]

        #arr_2d = arr_2d.values.reshape((5, 20, 17520))
        df_1d = pd.DataFrame(arr_1d, columns=[var_name])

        df_1d = pd.concat([self.dF.reset_index(), df_1d], axis = 1)

        t_stop = perf_counter()
        print(f"Done! ({np.round(t_stop - t1_start, 1)} sec.)")

        return df_1d

    def read_all_1D(self):

        # Reading in all output data into dataframes.
        # This could be improved at one point...
        print(f"     Reading all 1D variables... ", end='')
        t1_start = perf_counter()

        self.Datasets_1D = {}

        for name in self.output_cat_names:

            vars = self.files[name].data_vars

            df_vars_1D = []
            names_vars_1D = []

            for var in vars:

                dim = len(self.files[name][var].shape)
                if (var != 'time') &(var != 'soil_depth')& (dim == 1):
                    names_vars_1D.append(var);
                    df_vars_1D.append(self.files[name][var].to_dataframe())

            self.Datasets_1D[name] = pd.concat((df_vars_1D), axis=1,  ignore_index=True)
            self.Datasets_1D[name].columns = names_vars_1D
            self.Datasets_1D[name] = pd.concat([self.dF.reset_index(), self.Datasets_1D[name].reset_index()], axis = 1)


        t_stop = perf_counter()
        print(f"Done! ({np.round(t_stop - t1_start, 1)} sec.)")

    def read_2D(self, cat_name, var_name):
        arr_2d = self.files[cat_name][var_name]

        #arr_2d = arr_2d.values.reshape((5, 20, 17520))
        df_2d = pd.DataFrame(arr_2d, columns=[str(i) for i in range(arr_2d.shape[1])])

        df_2d = pd.concat([self.dF.reset_index(), df_2d], axis = 1)
        return df_2d

    def close(self):
        for name in self.output_cat_names:
            self.files[name].close()

    def _int2strZ(self, number):
        if number < 10:
            return "0" + str(number)
        else:
            return str(number)

