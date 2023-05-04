"""
This file contains routines to create some test patterns
to establish the correct kerf size of your laser
"""

import wx

from meerk40t.core.node.op_cut import CutOpNode
from meerk40t.core.node.op_raster import RasterOpNode
from meerk40t.core.units import ACCEPTED_UNITS, Length
from meerk40t.gui.icons import STD_ICON_SIZE, icons8_detective_50, icons8_hinges_50
from meerk40t.gui.mwindow import MWindow
from meerk40t.gui.wxutils import StaticBoxSizer, TextCtrl
from meerk40t.svgelements import Color, Rect, Circle, Polyline, Point

_ = wx.GetTranslation


class KerfPanel(wx.Panel):
    """
    UI for KerfTest, allows setting of parameters
    """

    def __init__(self, *args, context=None, **kwds):
        # begin wxGlade: clsLasertools.__init__
        kwds["style"] = kwds.get("style", 0) | wx.TAB_TRAVERSAL
        wx.Panel.__init__(self, *args, **kwds)
        self.context = context

        self.text_speed = TextCtrl(self, wx.ID_ANY, limited=True, check="float")
        self.text_speed.set_range(0, 1000)
        self.text_power = TextCtrl(self, wx.ID_ANY, limited=True, check="float")
        self.text_power.set_range(0, 1000)

        self.radio_pattern = wx.RadioBox(
            self,
            wx.ID_ANY,
            _("Pattern"),
            choices=(_("Rectangular (box joints)"), _("Circular (inlays)")),
        )
        self.spin_count = wx.SpinCtrl(self, wx.ID_ANY, initial=5, min=1, max=100)
        self.text_min = TextCtrl(self, wx.ID_ANY, limited=True, check="length")
        self.text_max = TextCtrl(self, wx.ID_ANY, limited=True, check="length")
        self.text_dim = TextCtrl(self, wx.ID_ANY, limited=True, check="length")
        # self.text_dim.set_range(0, 50)
        self.text_delta = TextCtrl(self, wx.ID_ANY, limited=True, check="length")
        # self.text_delta.set_range(0, 50)

        self.button_create = wx.Button(self, wx.ID_ANY, _("Create Pattern"))
        self.button_create.SetBitmap(icons8_detective_50.GetBitmap(resize=25))

        self._set_layout()
        self._set_logic()
        self._set_defaults()
        # Check for appropriate values
        self.on_valid_values(None)
        self.Layout()

    def _set_defaults(self):
        self.radio_pattern.SetSelection(0)
        self.spin_count.SetValue(5)
        self.text_dim.SetValue("20mm")
        self.text_delta.SetValue("5mm")
        self.text_speed.SetValue("5")
        self.text_power.SetValue("1000")
        self.text_min.SetValue("0.05mm")
        self.text_max.SetValue("0.25mm")

    def _set_logic(self):
        self.button_create.Bind(wx.EVT_BUTTON, self.on_button_generate)
        self.spin_count.Bind(wx.EVT_SPIN, self.on_valid_values)
        self.text_delta.Bind(wx.EVT_TEXT, self.on_valid_values)
        self.text_min.Bind(wx.EVT_TEXT, self.on_valid_values)
        self.text_max.Bind(wx.EVT_TEXT, self.on_valid_values)
        self.text_dim.Bind(wx.EVT_TEXT, self.on_valid_values)
        self.text_dim.Bind(wx.EVT_TEXT, self.on_valid_values)
        self.text_speed.Bind(wx.EVT_TEXT, self.on_valid_values)
        self.text_power.Bind(wx.EVT_TEXT, self.on_valid_values)

    def _set_layout(self):
        def size_it(ctrl, value):
            ctrl.SetMaxSize(wx.Size(int(value), -1))
            ctrl.SetMinSize(wx.Size(int(value * 0.75), -1))
            ctrl.SetSize(wx.Size(value, -1))

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        sizer_cutop = StaticBoxSizer(self, wx.ID_ANY, _("Cut-Operation"), wx.HORIZONTAL)
        sizer_speed = StaticBoxSizer(self, wx.ID_ANY, _("Speed"), wx.HORIZONTAL)
        sizer_power = StaticBoxSizer(self, wx.ID_ANY, _("Power"), wx.HORIZONTAL)
        sizer_speed.Add(self.text_speed, 1, wx.EXPAND, 0)
        sizer_power.Add(self.text_power, 1, wx.EXPAND, 0)
        sizer_cutop.Add(sizer_speed, 1, wx.EXPAND, 0)
        sizer_cutop.Add(sizer_power, 1, wx.EXPAND, 0)

        sizer_param = StaticBoxSizer(self, wx.ID_ANY, _("Parameters"), wx.VERTICAL)

        hline_type = wx.BoxSizer(wx.HORIZONTAL)
        hline_type.Add(self.radio_pattern, 0, wx.EXPAND, 0)
        hline_count = wx.BoxSizer(wx.HORIZONTAL)
        mylbl = wx.StaticText(self, wx.ID_ANY, _("Count:"))
        size_it(mylbl, 85)
        hline_count.Add(mylbl, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        hline_count.Add(self.spin_count, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        hline_min = wx.BoxSizer(wx.HORIZONTAL)
        mylbl = wx.StaticText(self, wx.ID_ANY, _("Minimum:"))
        size_it(mylbl, 85)
        hline_min.Add(mylbl, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        hline_min.Add(self.text_min, 1, wx.ALIGN_CENTER_VERTICAL, 0)

        hline_max = wx.BoxSizer(wx.HORIZONTAL)
        mylbl = wx.StaticText(self, wx.ID_ANY, _("Maximum:"))
        size_it(mylbl, 85)
        hline_max.Add(mylbl, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        hline_max.Add(self.text_max, 1, wx.ALIGN_CENTER_VERTICAL, 0)

        hline_dim = wx.BoxSizer(wx.HORIZONTAL)
        mylbl = wx.StaticText(self, wx.ID_ANY, _("Size:"))
        size_it(mylbl, 85)
        hline_dim.Add(mylbl, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        hline_dim.Add(self.text_dim, 1, wx.ALIGN_CENTER_VERTICAL, 0)

        hline_delta = wx.BoxSizer(wx.HORIZONTAL)
        mylbl = wx.StaticText(self, wx.ID_ANY, _("Delta:"))
        size_it(mylbl, 85)
        hline_delta.Add(mylbl, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        hline_delta.Add(self.text_delta, 1, wx.ALIGN_CENTER_VERTICAL, 0)

        sizer_param.Add(hline_type, 0, wx.EXPAND, 0)
        sizer_param.Add(hline_count, 0, wx.EXPAND, 0)
        sizer_param.Add(hline_min, 0, wx.EXPAND, 0)
        sizer_param.Add(hline_max, 0, wx.EXPAND, 0)
        sizer_param.Add(hline_dim, 0, wx.EXPAND, 0)
        sizer_param.Add(hline_delta, 0, wx.EXPAND, 0)

        sizer_info = StaticBoxSizer(self, wx.ID_ANY, _("How to use it"), wx.VERTICAL)
        infomsg = _(
            "If you want to produce cut out shapes with *exact* dimensions"
            + " after the burn, then you need to take the width of the"
            + " laserbeam into consideration (aka Kerf).\n"
            + "This routine will create a couple of testshapes for you to establish this value.\n"
            + "After you cut these shapes out you need to try to fit shapes with the same"
            + " label together. Choose the one that have a perfect fit and use the"
            + " label as your kerf-value."
        )
        info_label = wx.TextCtrl(
            self, wx.ID_ANY, value=infomsg, style=wx.TE_READONLY | wx.TE_MULTILINE
        )
        info_label.SetBackgroundColour(self.GetBackgroundColour())
        sizer_info.Add(info_label, 1, wx.EXPAND, 0)

        main_sizer.Add(sizer_cutop, 0, wx.EXPAND, 1)
        main_sizer.Add(sizer_param, 0, wx.EXPAND, 1)
        main_sizer.Add(self.button_create, 0, 0, 0)
        main_sizer.Add(sizer_info, 1, wx.EXPAND, 0)
        main_sizer.Layout()

        self.text_min.SetToolTip(_("Minimum value for Kerf"))
        self.text_max.SetToolTip(_("Maximum value for Kerf"))
        self.text_dim.SetToolTip(_("Dimension of the to be created pattern"))
        self.text_delta.SetToolTip(_("Horizontal gap between patterns"))

        self.button_create.SetToolTip(_("Create a test-pattern with your values"))

        self.SetSizer(main_sizer)

    def on_button_close(self, event):
        self.context("window close Kerftest\n")

    def on_valid_values(self, event):
        def valid_length(control):
            res = False
            d = control.GetValue()
            if d != "":
                try:
                    test = float(Length(d))
                    res = True
                except ValueError:
                    pass
            return res

        def valid_float(control, minv, maxv):
            res = False
            d = control.GetValue()
            if d != "":
                try:
                    test = float(d)
                    if minv <= test <= maxv:
                        res = True
                except ValueError:
                    pass
            return res

        is_valid = True
        if self.spin_count.GetValue() < 1:
            is_valid = False
        if not valid_length(self.text_delta):
            is_valid = False
        if not valid_length(self.text_dim):
            is_valid = False
        if not valid_length(self.text_min):
            is_valid = False
        if not valid_length(self.text_max):
            is_valid = False
        if not valid_float(self.text_power, 0, 1000):
            is_valid = False
        if not valid_float(self.text_speed, 0, 1000):
            is_valid = False

        if is_valid:
            try:
                minv = float(Length(self.text_min.GetValue()))
                maxv = float(Length(self.text_max.GetValue()))
                if minv > maxv or minv < 0 or maxv < 0:
                    is_valid = False
            except ValueError:
                is_valid = False
        self.button_create.Enable(is_valid)

    def on_button_generate(self, event):
        def make_color(idx, maxidx, colidx):
            r = 0
            g = 0
            b = 0
            if colidx == "r":
                r = int(255 / maxidx * idx)
            elif colidx == "g":
                g = int(255 / maxidx * idx)
            elif colidx == "b":
                b = int(255 / maxidx * idx)
            mycolor = Color(r, g, b)
            return mycolor

        def clear_all():
            self.context.elements.clear_operations(fast=True)
            self.context.elements.clear_elements(fast=True)

        def create_operations():
            def shortened(value, digits):
                result = str(round(value, digits))
                if "." in result:
                    while result.endswith("0"):
                        result = result[:-1]
                if result.endswith("."):
                    if result == ".":
                        result = "0"
                    else:
                        result = result[:-1]
                return result

            display_labels = True
            display_values = True
            kerf = minv
            if count < 2:
                delta = maxv - minv
            else:
                delta = (maxv - minv) / (count - 1)
            operation_branch = self.context.elements.op_branch
            element_branch = self.context.elements.elem_branch
            text_op = RasterOpNode()
            text_op.color = Color("black")
            text_op.label = "Descriptions"
            xx = 0
            yy = 0
            shape0 = None
            shape1 = None
            shape2 = None
            if rectangular:
                shape0 = None
                elem0 = None
                shape1 = Polyline(
                    (
                        (0.0 * pattern_size, 0.0 * pattern_size),
                        (1.0 * pattern_size, 0.0 * pattern_size),
                        (1.0 * pattern_size, 0.5 * pattern_size),
                        (0.7 * pattern_size, 0.5 * pattern_size),
                        (0.7 * pattern_size, 0.2 * pattern_size),
                        (0.3 * pattern_size, 0.2 * pattern_size),
                        (0.3 * pattern_size, 0.5 * pattern_size),
                        (0.0 * pattern_size, 0.5 * pattern_size),
                        (0.0 * pattern_size, 0.0 * pattern_size),
                    )
                )
                elem1 = "elem polyline"
                shape2 = Polyline(
                    (
                        (0.0 * pattern_size, 0.5 * pattern_size),
                        (0.3 * pattern_size, 0.5 * pattern_size),
                        (0.3 * pattern_size, 0.2 * pattern_size),
                        (0.7 * pattern_size, 0.2 * pattern_size),
                        (0.7 * pattern_size, 0.5 * pattern_size),
                        (1.0 * pattern_size, 0.5 * pattern_size),
                        (1.0 * pattern_size, 1.0 * pattern_size),
                        (0.0 * pattern_size, 1.0 * pattern_size),
                        (0.0 * pattern_size, 0.5 * pattern_size),
                    )
                )
                elem2 = "elem polyline"
            else:
                shape0 = Rect(x=0, y=0, width=pattern_size, height=pattern_size)
                elem0 = "elem rect"
                shape1 = Circle(
                    cx= 0.5 * pattern_size,
                    cy = 0.5 * pattern_size,
                    rx = 0.3 * pattern_size,
                    ry = 0.3 * pattern_size,
                )
                elem1 = "elem ellipse"
                shape2 = Circle(
                    cx= 0.5 * pattern_size,
                    cy = 0.5 * pattern_size,
                    rx = 0.3 * pattern_size,
                    ry = 0.3 * pattern_size,
                )
                elem2 = "elem ellipse"
            for idx in range(count - 1):
                op_col1 = make_color(idx, count, "r")
                op_col2 = make_color(idx, count, "g")

                kerlen = Length(kerf)
                op1 = CutOpNode(label=f"Inner {shortened(kerlen.mm, 3)}mm")
                op1.color = op_col1
                op1.speed = op_speed
                op1.speed = op_power
                op1.kerf = -1 * kerf
                operation_branch.add_node(op1)
                if shape0 is not None:
                    node = element_branch.add(shape=shape0, type=elem0)
                    node.stroke = op_col1
                    node.stroke_width = 500
                    node.matrix.post_translate(xx, yy)
                    node.modified()
                    op1.add_reference(node, 0)
                if shape1 is not None:
                    node = element_branch.add(shape=shape1, type=elem1)
                    node.stroke = op_col1
                    node.stroke_width = 500
                    node.matrix.post_translate(xx, yy)
                    node.modified()
                    op1.add_reference(node, 0)

                op2 = CutOpNode(label=f"Outer {shortened(kerlen.mm, 3)}mm")
                op2.color = op_col2
                op2.speed = op_speed
                op2.speed = op_power
                op2.kerf = +1 * kerf
                operation_branch.add_node(op2)
                if shape2 is not None:
                    node = element_branch.add(shape=shape2, type=elem2)
                    node.stroke = op_col2
                    node.stroke_width = 500
                    node.matrix.post_translate(xx, yy + pattern_size + gap_size)
                    node.modified()
                    op2.add_reference(node, 0)

                kerf += delta
                xx += pattern_size
                xx += gap_size

        try:
            minv = float(Length(self.text_min.GetValue()))
            maxv = float(Length(self.text_max.GetValue()))
            op_speed = float(self.text_speed.GetValue())
            op_power = float(self.text_power.GetValue())
            gap_size = float(Length(self.text_delta.GetValue()))
            count = self.spin_count.GetValue()
            if count < 2:
                count = 1
                maxv = minv
            pattern_size = float(Length(self.text_dim.GetValue()))
            rectangular =  bool(self.radio_pattern.GetSelection() == 0)
        except ValueError:
            return

        message = _("This will delete all existing operations and elements") + "\n"
        message += (
            _("and replace them by the test-pattern! Are you really sure?") + "\n"
        )
        message += _("(Yes=Empty and Create, No=Keep existing)")
        caption = _("Create Test-Pattern")
        dlg = wx.MessageDialog(
            self,
            message,
            caption,
            wx.YES_NO | wx.CANCEL | wx.ICON_WARNING,
        )
        result = dlg.ShowModal()
        dlg.Destroy()
        if result == wx.ID_YES:
            clear_all()
        elif result == wx.ID_CANCEL:
            return

        create_operations()

        self.context.signal("rebuild_tree")
        self.context.signal("refresh_scene", "Scene")

    def pane_show(self):
        return


class KerfTool(MWindow):
    """
    LivingHingeTool is the wrapper class to setup the
    required calls to open the HingePanel window
    In addition it listens to element selection and passes this
    information to HingePanel
    """

    def __init__(self, *args, **kwds):
        super().__init__(570, 420, submenu="Laser-Tools", *args, **kwds)
        self.panel_template = KerfPanel(
            self,
            wx.ID_ANY,
            context=self.context,
        )
        self.add_module_delegate(self.panel_template)
        _icon = wx.NullIcon
        _icon.CopyFromBitmap(icons8_hinges_50.GetBitmap())
        self.SetIcon(_icon)
        self.SetTitle(_("Kerf-Test"))
        self.Layout()

    def window_open(self):
        self.panel_template.pane_show()

    def window_close(self):
        pass

    @staticmethod
    def submenu():
        return ("Laser-Tools", "Kerf-Test")
