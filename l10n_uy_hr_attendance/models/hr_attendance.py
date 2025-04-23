# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions, _

class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    uy_note = fields.Char("Note")
    uy_normal_hours = fields.Float("Normal Hrs", compute='_compute_uy_hours', readonly=True)
    uy_extra_hours = fields.Float("Extra Hrs", compute='_compute_uy_hours', readonly=True)
    uy_rain_hours = fields.Float("Rain Hrs", compute="_compute_uy_rain_hours")
    uy_break = fields.Boolean("Break")
    department_id = fields.Many2one('hr.department', related="employee_id.department_id",
                                    depends=["employee_id"], store=True)

    @api.depends('department_id', 'check_in', 'check_out', 'uy_break')
    def _compute_uy_rain_hours(self):
        for attendance in self:
            if attendance.check_in and attendance.check_out:
                query = """SELECT id FROM uy_rain_hours  WHERE department_id=%s
                        AND (check_in BETWEEN %s AND %s OR check_out BETWEEN %s AND %s)
                        OR (check_in<%s AND check_out>%s);"""
                self.env.cr.execute(query, [attendance.department_id.id, attendance.check_in,
                                            attendance.check_out, attendance.check_in,
                                            attendance.check_out,attendance.check_in,
                                            attendance.check_out])
                rain_vals = self.env.cr.fetchall()
                rains = []
                for rain_val in rain_vals:
                    rains.append(rain_val[0])
                rain_ids = rain_vals and self.env['uy.rain.hours'].browse(rains) or False
                delta = 0.0
                if rain_ids:
                    for rain_id in rain_ids:
                        if rain_id.check_in <= attendance.check_in <= rain_id.check_out \
                                and rain_id.check_in <= attendance.check_out <= rain_id.check_out:
                            temp_delta = attendance.check_out - attendance.check_in
                        elif rain_id.check_in>=attendance.check_in and rain_id.check_out<=attendance.check_out:
                            temp_delta = rain_id.check_out - rain_id.check_in
                        elif rain_id.check_in>=attendance.check_in:
                            temp_delta = attendance.check_out - rain_id.check_in
                        else:
                            temp_delta = rain_id.check_out - attendance.check_in
                        delta += (temp_delta.total_seconds()) / 3600.0
                attendance.uy_rain_hours = delta
            else:
                attendance.uy_rain_hours = False


    @api.depends('check_in', 'check_out', 'uy_break')
    def _compute_uy_hours(self):
        for attendance in self:
            if attendance.check_out and attendance.check_in:
                break_hours = 0
                check_in_dt_start, check_in_day_start = attendance._get_day_start_and_day(attendance.employee_id, attendance.check_in)
                extra_hours = abs(sum(self.env['hr.attendance.overtime'].search([('employee_id', '=', attendance.employee_id.id),('date', '=', check_in_day_start)]).mapped('duration')))
                if not attendance.uy_break:
                    break_hours = 3600.0
                    if attendance.employee_id.company_id.hr_attendance_overtime:
                        extra_hours -= break_hours/3600.0
                delta = attendance.check_out - attendance.check_in

                attendance.uy_extra_hours = extra_hours
                attendance.uy_normal_hours = (delta.total_seconds() - break_hours) / 3600.0 - attendance.uy_rain_hours
            else:
                attendance.uy_normal_hours = False
                attendance.uy_extra_hours = False
