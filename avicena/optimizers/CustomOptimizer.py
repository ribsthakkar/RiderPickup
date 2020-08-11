from avicena.optimizers import GeneralOptimizer


class CustomOptimizer(GeneralOptimizer):
    def __init__(self, trips, drivers, name, config):
        super().__init__(trips, drivers, name, config)
        self.add_custom_constraints()

    def add_custom_constraints(self):
        print("Adding Custom Defined Constraints")

        """
        Route Length Penalty
        """
        for d in self.drivers:
            otime = 0
            itime = 0
            for dS in self.driver_starts:
                if dS[:-4] != d.address[:-4]:
                    continue
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[dS]):
                    otime += self.time_vars[d][otrip]
                break
            for dE in self.driver_ends:
                if dE[:-4] != d.address[:-4]:
                    continue
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[dE]):
                    itime += self.time_vars[d][intrip]
                break
            self.obj += self.ROUTE_LIMIT_PEN * (itime - otime)
            if not d.ed:
                try:
                    c = self.mdl.add_constraint(otime >= self.EARLY_DAY_TIME)
                    self.ed_constr.add(c)
                    pass
                except DOcplexException as e:
                    if 'trivially' not in e.message:
                        raise e
                    print(itime, otime)
                    print("Can't restrict early day for", d.name)

        """
        Merge Trip Requirements
        """
        for d in self.drivers:
            for mer in self.filter_driver_feasible_trips(d, self.merges):
                self.mdl.add_constraint(ct =self.trip_vars[d][mer] == self.trip_vars[d][self.merges[mer]])
                self.obj += self.MERGE_PEN * (self.time_vars[d][mer] - (self.time_vars[d][self.merges[mer]] + self.merges[mer].lp.time * self.trip_vars[d][mer])) * (24)
        """
        Equalizing Revenue Penalty
        """
        self.rev_max = self.mdl.continuous_var(0)
        self.rev_min = self.mdl.continuous_var(0)
        for d in self.drivers:
            self.revenue_vars[d] = self.mdl.continuous_var(lb=0, name="Revenue" + str(d.id))
            self.mdl.add_constraint(self.revenue_vars[d] == sum(self.revenues[t.lp.o] * self.trip_vars[d][t] for t in self.filter_driver_feasible_trips(d, self.all_trips.values())))
            self.mdl.add_constraint(self.rev_max >= self.revenue_vars[d])
            self.mdl.add_constraint(self.rev_min <= self.revenue_vars[d])
        self.obj += self.REVENUE_PEN * (self.rev_max - self.rev_min)

        """
        Equalizing Wheel Chair Trip Penalty
        """
        self.w_max = self.mdl.continuous_var(0)
        self.w_min = self.mdl.continuous_var(0)
        for d in self.drivers:
            if 'W' not in d.los: continue
            self.wheelchair_vars[d] = self.mdl.continuous_var(lb=0, name="Wheelchairs" + str(d.id))
            self.mdl.add_constraint(self.wheelchair_vars[d] == sum(self.trip_vars[d][t] for t in filter(lambda x: x.los == 'W', self.filter_driver_feasible_trips(d, self.all_trips.values()))))
            self.mdl.add_constraint(self.w_max >= self.wheelchair_vars[d])
            self.mdl.add_constraint(self.w_min <= self.wheelchair_vars[d])
        self.obj += self.W_PEN * (self.w_max - self.w_min)