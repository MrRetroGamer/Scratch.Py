from __future__ import annotations

from ..util import jscompat as cast
from . import api, command, reporter


@reporter("data_variable")
def data_variable(rt, tgt, block):
    container = rt.field_var_container(tgt, block, "VARIABLE")
    return container[1]


@command("data_setvariableto")
def setvariableto(rt, tgt, block):
    container = rt.field_var_container(tgt, block, "VARIABLE")
    container[1] = api.val(rt, tgt, block, "VALUE")


@command("data_changevariableby")
def changevariableby(rt, tgt, block):
    container = rt.field_var_container(tgt, block, "VARIABLE")
    delta = cast.to_number(api.val(rt, tgt, block, "VALUE", 0))
    current = cast.to_number(container[1])
    if isinstance(current, int) and isinstance(delta, int):
        container[1] = current + delta
    else:
        container[1] = float(current) + float(delta)


@command("data_showvariable")
def showvariable(rt, tgt, block):
    _set_monitor_visible(rt, block, "VARIABLE", True)


@command("data_hidevariable")
def hidevariable(rt, tgt, block):
    _set_monitor_visible(rt, block, "VARIABLE", False)


@command("data_showlist")
def showlist(rt, tgt, block):
    _set_monitor_visible(rt, block, "LIST", True)


@command("data_hidelist")
def hidelist(rt, tgt, block):
    _set_monitor_visible(rt, block, "LIST", False)


def _set_monitor_visible(rt, block, field_name: str, visible: bool):
    entry = block.fields.get(field_name)
    if not entry:
        return
    name = entry[0]
    sprite_name = None if rt.current_thread is None else rt.current_thread.target.name
    for monitor in rt.monitors:
        params = monitor.params
        key = "VARIABLE" if field_name == "VARIABLE" else "LIST"
        if params.get(key) == name:
            monitor_owner = monitor.sprite_name
            if monitor_owner == sprite_name or (sprite_name and monitor_owner is None):
                monitor.visible = visible


@reporter("data_listcontents")
def listcontents(rt, tgt, block):
    container = rt.field_list_container(tgt, block, "LIST")
    return container[1]


@command("data_addtolist")
def addtolist(rt, tgt, block):
    container = rt.field_list_container(tgt, block, "LIST")
    container[1].append(api.val(rt, tgt, block, "ITEM"))


@command("data_deleteoflist")
def deleteoflist(rt, tgt, block):
    container = rt.field_list_container(tgt, block, "LIST")
    items = container[1]
    index = cast.to_list_index(api.val(rt, tgt, block, "INDEX"), len(items))
    text = cast.to_string(api.val(rt, tgt, block, "INDEX")).lower()
    if text == "all":
        items.clear()
    elif text == "last":
        if items:
            items.pop()
    elif index is not None:
        items.pop(index - 1)


@command("data_deletealloflist")
def deletealloflist(rt, tgt, block):
    container = rt.field_list_container(tgt, block, "LIST")
    container[1].clear()


@command("data_insertatlist")
def insertatlist(rt, tgt, block):
    container = rt.field_list_container(tgt, block, "LIST")
    items = container[1]
    index = cast.to_list_index(api.val(rt, tgt, block, "INDEX"), len(items) + 1)
    if index is not None:
        items.insert(index - 1, api.val(rt, tgt, block, "ITEM"))


@command("data_replaceitemoflist")
def replaceitemoflist(rt, tgt, block):
    container = rt.field_list_container(tgt, block, "LIST")
    items = container[1]
    index = cast.to_list_index(api.val(rt, tgt, block, "INDEX"), len(items))
    if index is not None:
        items[index - 1] = api.val(rt, tgt, block, "ITEM")


@reporter("data_itemoflist")
def itemoflist(rt, tgt, block):
    container = rt.field_list_container(tgt, block, "LIST")
    items = container[1]
    index = cast.to_list_index(api.val(rt, tgt, block, "INDEX"), len(items))
    if index is None:
        return ""
    return items[index - 1]


@reporter("data_itemnumoflist")
def itemnumoflist(rt, tgt, block):
    container = rt.field_list_container(tgt, block, "LIST")
    item = api.val(rt, tgt, block, "ITEM")
    for i, existing in enumerate(container[1]):
        if cast.equals(existing, item):
            return i + 1
    return 0


@reporter("data_lengthoflist")
def lengthoflist(rt, tgt, block):
    container = rt.field_list_container(tgt, block, "LIST")
    return len(container[1])


@reporter("data_listcontainsitem")
def listcontainsitem(rt, tgt, block):
    container = rt.field_list_container(tgt, block, "LIST")
    item = api.val(rt, tgt, block, "ITEM")
    return any(cast.equals(existing, item) for existing in container[1])
