from meerk40t.core.cutcode.inputcut import InputCut
from meerk40t.core.element_types import *
from meerk40t.core.node.node import Node


class InputOperation(Node):
    """
    InputOperation sets GPIO values.

    Node type "util input"
    """

    def __init__(self, **kwargs):
        self.input_mask = 0
        self.input_value = 0
        self.input_message = None
        self.output = True
        super().__init__(type="util input", **kwargs)
        self._formatter = "{enabled}{element_type} {bits}"

    def __repr__(self):
        return f"InputOperation('{self.input_mask}')"

    def __len__(self):
        return 1

    def bitstring(self):
        mask = self.input_mask
        # value = self.input_value
        value = -1 if self.input_value else 0
        bits = bytearray(b"X" * 16)
        for m in range(16):
            if (mask >> m) & 1:
                bits[m] = ord("1") if (value >> m) & 1 else ord("0")
        return bits.decode("utf8")

    @property
    def implicit_passes(self):
        return 1

    def get_mask(self, bit=None):
        if bit is None:
            return self.input_mask
        return (self.input_mask >> bit) & 1

    def get_value(self, bit=None):
        if bit is None:
            return self.input_value
        return (self.input_value >> bit) & 1

    def mask_toggle(self, bit):
        self.input_mask = self.input_mask ^ (1 << bit)

    def mask_on(self, bit):
        self.input_mask = self.input_mask | (1 << bit)

    def mask_off(self, bit):
        self.input_mask = ~((~self.input_mask) | (1 << bit))

    def value_toggle(self, bit):
        self.input_value = self.input_value ^ (1 << bit)

    def value_on(self, bit):
        self.input_value = self.input_value | (1 << bit)

    def value_off(self, bit):
        self.input_value = ~((~self.input_value) | (1 << bit))

    def default_map(self, default_map=None):
        default_map = super().default_map(default_map=default_map)
        default_map["element_type"] = "Input"
        default_map["enabled"] = "(Disabled) " if not self.output else ""
        default_map["mask"] = self.input_mask
        default_map["value"] = self.input_value
        default_map["message"] = self.input_message
        default_map["bits"] = self.bitstring()
        default_map.update(self.__dict__)
        return default_map

    def drop(self, drag_node, modify=True):
        drop_node = self
        if drag_node.type in op_nodes:
            if modify:
                drop_node.insert_sibling(drag_node)
            return True
        elif drop_node.type == "branch ops":
            # Dragging operation to op branch to effectively move to bottom.
            if modify:
                drop_node.append_child(drag_node)
            return True
        return False

    def as_cutobjects(self, closed_distance=15, passes=1):
        """
        Generator of cutobjects for a raster operation. This takes any image node children
        and converts them into rastercut objects. These objects should have already been converted
        from vector shapes.

        The preference for raster shapes is to use the settings set on this operation rather than on the image-node.
        """
        input = InputCut(self.input_mask, self.input_value, self.input_message)
        input.original_op = self.type
        yield input
