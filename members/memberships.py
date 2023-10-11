from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta

class PlayerMembership(models.Model):
    _inherit = 'res.partner'

    @api.multi
    def set_expiry_date(self):
        self.ensure_one()
        self.write({'expiry_date': fields.Date.today()})

    d_o_b = fields.Date(string ='Date Of Birth')
    age = fields.Char(readonly=True,string='Age',store='True',compute='_compute_dob')
    highest_break_p = fields.Char(string='Highest Break(prac)')
    highest_break_m = fields.Char(string='Highest Break(match)')
    achievements = fields.Text()
    gdpr_box = fields.Boolean(string='GDPR Confirmation')
    eir_code = fields.Char(string='EIR code')
    over_21 = fields.Selection([(0,'0-10'),(1,'10-20'),(2,'20-30'),(3,'30-40'),(4,'40-50'),(5,'50-60'),(6,'60-70'),(7,'70-80'),(8,'80-90'),(9,'90-100')],string='21 and Over')
    under_21 = fields.Selection([(0,'0-10'),(1,'10-20')],string='Under 21')
    ladies = fields.Selection([(0,'0-10'),(1,'10-20')],string='Ladies')
    joining_date = fields.Date(compute='_compute_date_joining', store=True)
    expiry_date = fields.Date(string="Expiry date",compute='_compute_date_expiry',search='_search_date_expiry', store=True)
    club_name = fields.Char(string='Club Name')
    table_lines = fields.One2many('membership.membership_line','table_member_id', string='Tables')
    table_product_id=fields.Many2one('product.template',domain="[('table','=',True), ('type', '=', 'service')]")
    membership_product_id=fields.Many2one('product.template',string="Product" ,domain="[('membership','=',True), ('type', '=', 'service')]")
    membership_type = fields.Selection(selection=[('player', 'Player Membership'), ('club', 'Club Membership')])
    club_number_1 = fields.Char()
    club_number_2 = fields.Char()
    state = fields.Selection([
        ('running', 'Running'),
        ('expired', 'Expired'),
        ], string='Status', copy=False, index=True, track_visibility='onchange', default='running')
    membership_product = fields.Many2one('product.product', string="Membership Product", compute='get_membership_product',store=True)
    number_of_table = fields.Integer("Number Of Tables")
    
    @api.multi
    @api.depends('member_lines')
    def get_membership_product(self):
        for rec in self:
            if rec.member_lines:
                for line in rec.member_lines:
                    if line.membership_id:
                        rec.membership_product = line.membership_id.id
    
    
    @api.depends('d_o_b')
    def _compute_dob(self):
        for a in self:
            if a.d_o_b:
                date1=fields.Date.from_string(a.d_o_b)
                date_diff=relativedelta(date.today(),date1)
                a.age=str(date_diff.years)+" years "

    @api.depends('member_lines','table_lines')
    def _compute_date_joining(self):
        for rec in self:
            if rec.member_lines:
                if rec.member_lines[0]:
                    rec.joining_date = rec.member_lines[0].joining_date
        for rec_1 in self:
            if rec_1.table_lines:
                if rec_1.table_lines[0]:
                    rec_1.joining_date = rec_1.table_lines[0].joining_date

    @api.model
    def _search_date_expiry(self, operator, value):
        id_list = []
        if operator == '>=':
            for member in self.env['res.partner'].sudo().search([]):
                if member.member_lines:
                    if member.member_lines[0].expiry_date >= fields.Date.today():
                        id_list.append(member.id)
        else:
            for member in self.env['res.partner'].sudo().search([]):
                if member.member_lines:
                    if member.member_lines[0].expiry_date < fields.Date.today():
                        id_list.append(member.id)
        return [('id', 'in',id_list)]


    @api.depends('member_lines','table_lines')
    def _compute_date_expiry(self):
        for rec in self:
            if rec.member_lines:
                if rec.member_lines[0]:
                    rec.expiry_date = rec.member_lines[0].expiry_date
        for rec_1 in self:
            if rec_1.table_lines:
                if rec_1.table_lines[0]:
                    rec_1.expiry_date = rec_1.table_lines[0].expiry_date
    
    @api.depends('member_lines.account_invoice_line.invoice_id.state',
                 'member_lines.account_invoice_line.invoice_id.invoice_line_ids',
                 'member_lines.account_invoice_line.invoice_id.payment_ids',
                 'member_lines.account_invoice_line.invoice_id.payment_move_line_ids',
                 'member_lines.account_invoice_line.invoice_id.partner_id',
                 'free_member','associate_member',
                 'table_lines.account_invoice_line.invoice_id.state',
                 'table_lines.account_invoice_line.invoice_id.invoice_line_ids',
                 'table_lines.account_invoice_line.invoice_id.payment_ids',
                 'table_lines.account_invoice_line.invoice_id.payment_move_line_ids',
                 'table_lines.account_invoice_line.invoice_id.partner_id',)

    def _compute_membership_state(self):
        return super(PlayerMembership, self)._compute_membership_state()

    def _membership_state(self):
        res=super(PlayerMembership, self)._membership_state()
        today = fields.Date.today()
        if self.membership_type == 'player':
            for partner in self:
                if partner.expiry_date and today > partner.expiry_date:
                    partner.state = 'expired'
                if partner.associate_member:
                    res_state = partner.associate_member._membership_state()
                    res[partner.id] = res_state[partner.associate_member.id]
                s = 4
                if partner.member_lines:
                    for mline in partner.member_lines:
                        if (mline.expiry_date or date.min) >= today and (mline.joining_date or date.min) <= today:
                            if mline.account_invoice_line.invoice_id.partner_id == partner:
                                mstate = mline.account_invoice_line.invoice_id.state
                                if mstate == 'paid':
                                    s = 0
                                    inv = mline.account_invoice_line.invoice_id
                                    for ml in inv.payment_move_line_ids:
                                        if any(ml.invoice_id.filtered(lambda inv: inv.type == 'out_refund')):
                                            s = 2
                                    break
                                elif mstate == 'open' and s != 0:
                                    s = 1
                                elif mstate == 'cancel' and s != 0 and s != 1:
                                    s = 2
                                elif mstate == 'draft' and s != 0 and s != 1:
                                    s = 3
                    if s == 4:
                        for mline in partner.member_lines:
                            if (mline.joining_date or date.min) < today and (mline.expiry_date or date.min) < today and (mline.expiry_date or date.min) <= (mline.expiry_date or date.min) and mline.account_invoice_line and mline.account_invoice_line.invoice_id.state == 'paid':
                                s = 5
                            else:
                                s = 6
                    if s == 0:
                        res[partner.id] = 'paid'
                    elif s == 1:
                        res[partner.id] = 'invoiced'
                    elif s == 2:
                        res[partner.id] = 'canceled'
                    elif s == 3:
                        res[partner.id] = 'waiting'
                    elif s == 5:
                        res[partner.id] = 'old'
                    elif s == 6:
                        res[partner.id] = 'none'
                if partner.free_member and s != 0:
                    res[partner.id] = 'free'
        elif self.membership_type == 'club':
            for table_member_id in self:
                res[table_member_id.id] = 'none'
                s = 4
                if table_member_id.table_lines:
                    for mline in table_member_id.table_lines:
                        if (mline.expiry_date or date.min) >= today and (mline.joining_date or date.min) <= today:
                            if mline.account_invoice_line.invoice_id.partner_id == table_member_id:
                                mstate = mline.account_invoice_line.invoice_id.state
                                if mstate == 'paid':
                                    s = 0
                                    inv = mline.account_invoice_line.invoice_id
                                    for ml in inv.payment_move_line_ids:
                                        if any(ml.invoice_id.filtered(lambda inv: inv.type == 'out_refund')):
                                            s = 2
                                    break
                                elif mstate == 'open' and s != 0:
                                    s = 1
                                elif mstate == 'cancel' and s != 0 and s != 1:
                                    s = 2
                                elif mstate == 'draft' and s != 0 and s != 1:
                                    s = 3
                    if s == 4:
                        for mline in table_member_id.table_lines:
                            if (mline.joining_date or date.min) < today and (mline.expiry_date or date.min) < today and (mline.expiry_date or date.min) <= (mline.expiry_date or date.min) and mline.account_invoice_line and mline.account_invoice_line.invoice_id.state == 'paid':
                                s = 5
                            else:
                                s = 6
                    if s == 0:
                        res[table_member_id.id] = 'paid'
                    elif s == 1:
                        res[table_member_id.id] = 'invoiced'
                    elif s == 2:
                        res[table_member_id.id] = 'canceled'
                    elif s == 3:
                        res[table_member_id.id] = 'waiting'
                    elif s == 5:
                        res[table_member_id.id] = 'old'
                    elif s == 6:
                        res[table_member_id.id] = 'none'
        return res

    @api.multi
    def create_table_invoice(self, product_id=None, datas=None):
    
        product_id = product_id or datas.get('table_product_id')
        amount = datas.get('amount', 0.0)
        invoice_list = []
        for partner in self:
            addr = partner.address_get(['invoice'])
            if not addr.get('invoice', False):
                raise UserError(_("Partner doesn't have an address to make the invoice."))
            invoice = self.env['account.invoice'].create({
                'partner_id': partner.id,
                'account_id': partner.property_account_receivable_id.id,
                'fiscal_position_id': partner.property_account_position_id.id
            })
            line_values = {
                'product_id': product_id,
                'price_unit': amount,
                'invoice_id': invoice.id,
            }
            invoice_line = self.env['account.invoice.line'].new(line_values)
            invoice_line._onchange_product_id()
            line_values = invoice_line._convert_to_write({name: invoice_line[name] for name in invoice_line._cache})
            line_values['price_unit'] = amount
            invoice.write({'invoice_line_ids': [(0, 0, line_values)]})
            invoice_list.append(invoice.id)
            invoice.compute_taxes()
        return invoice_list

class MembershipLine(models.Model):
    _inherit = 'membership.membership_line'

    joining_date = fields.Date(default=fields.Date.today(),readonly=True)
    expiry_date = fields.Date(compute='_compute_expiry_date',store=True)
    table_member_id = fields.Many2one('res.partner', string='Tables', index=True)

    @api.depends('membership_id.duration_span', 'membership_id.duration', 'joining_date')
    def _compute_expiry_date(self):
        for rec in self:
            if rec.joining_date:
                if rec.membership_id.duration_span == 'day':
                    rec.expiry_date = rec.joining_date + relativedelta(days=rec.membership_id.duration + 1)
            elif rec.membership_id.duration_span == 'month':
                rec.expiry_date = rec.joining_date + relativedelta(months=rec.membership_id.duration, day=30)
            elif rec.membership_id.duration_span == 'year':
                rec.expiry_date = rec.joining_date.replace(month=6, day=30) + relativedelta(years=rec.membership_id.duration)
                rec.expiry_date = rec.expiry_date.replace(year=rec.joining_date.year + rec.membership_id.duration)


    
    @api.model
    def _process_expiry_state_change(self):
        data = self.env['membership.membership_line'].search([])
        for rec in data:
            if rec.expiry_date == fields.Date.today():
                rec.partner.write({'state' :'expired'})
        
    
    def open_member_invoice(self):
        a_id = self.env.ref("account.action_invoice_tree_pending_invoice").read()[0]
        view_id = self.env.ref("account.invoice_form").id
        return {
            'type': 'ir.actions.act_window',
            'name': _('member invoice'),
            'view_mode': 'form',
            'res_model': 'account.invoice',
            'res_id': self.account_invoice_id.id,
            'views': [[view_id, 'form']],
        }
        return False

    @api.multi
    def set_expiry_date(self):
        self.ensure_one()
        self.write({'expiry_date': fields.Date.today()})
    
   
