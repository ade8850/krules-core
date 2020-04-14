import inspect

import wrapt

from krules_core.subject import SubjectProperty, SubjectExtProperty, PayloadConst, PropertyType


class Subject(object):

    """
    Subject implemantation
    Needs a storage strategy implementation
    """

    def __init__(self, name, event_info={}, use_cache_dafault=True):
        from krules_core.providers import subject_storage_factory

        self.name = name
        self._use_cache = use_cache_dafault
        self._storage = subject_storage_factory(name)
        self._event_info = event_info
        self._cached = None

    def _load(self):

        props, ext_props = self._storage.load()
        #if self._cached is None:
        self._cached = \
            { PropertyType.DEFAULT: {
                "values": {},
                "created": set(),
                "updated": set(),
                "deleted": set(),
            }, PropertyType.EXTENDED: {
                "values": {},
                "created": set(),
                "updated": set(),
                "deleted": set(),
            }}
        self._cached[PropertyType.DEFAULT]["values"] = props
        self._cached[PropertyType.EXTENDED]["values"] = ext_props

    def _set(self, prop, value, is_ext, is_mute, use_cache):

        if use_cache is None:
            use_cache = self._use_cache
        if use_cache:
            if self._cached is None:
                self._load()
            kprops = is_ext and PropertyType.EXTENDED or PropertyType.DEFAULT
            vals = is_ext and self._cached[kprops]["values"] or self._cached[kprops]["values"]
            if prop in vals:
                self._cached[kprops]["updated"].add(prop)
            else:
                self._cached[kprops]["created"].add(prop)
            try:
                old_value = vals[prop]
            except KeyError:
                old_value = None
            if inspect.isfunction(value):
                n_params = len(inspect.signature(value).parameters)
                if n_params == 0:
                    value = value()
                elif n_params == 1:
                    value = value(old_value)
                else:
                    raise ValueError("to many arguments for {}".format(prop))

            vals[prop] = value
        else:
            klass, k = is_ext and (SubjectExtProperty, PropertyType.EXTENDED) or (SubjectProperty, PropertyType.DEFAULT)
            value, old_value = self._storage.set(klass(prop, value))
            # update cached
            if self._cached:
                self._cached[k]["values"][prop] = value
                if prop in self._cached[k]["created"]:
                    self._cached[k]["created"].remove(prop)
                if prop in self._cached[k]["updated"]:
                    self._cached[k]["updated"].remove(prop)
                if prop in self._cached[k]["deleted"]:
                    self._cached[k]["deleted"].remove(prop)

        if not is_mute:
            payload = {PayloadConst.PROPERTY_NAME: prop, PayloadConst.OLD_VALUE: old_value,
                       PayloadConst.VALUE: value}

            from krules_core.providers import message_router_factory
            from krules_core import messages
            message_router_factory().route(messages.SUBJECT_PROPERTY_CHANGED, self, payload)

        return value, old_value

    def set(self, prop, value, is_mute=False, use_cache=None):
        return self._set(prop, value, False, is_mute, use_cache)

    def set_ext(self, prop, value, use_cache=None):
        return self._set(prop, value, True, True, use_cache)

    def _get(self, prop, is_ext, use_cache):
        if use_cache is None:
            use_cache = self._use_cache
        if use_cache:
            if self._cached is None:
                self._load()
            if is_ext:
                vals = self._cached[PropertyType.EXTENDED]["values"]
            else:
                vals = self._cached[PropertyType.DEFAULT]["values"]
            if prop not in vals:
                raise AttributeError(prop)
            return vals[prop]
        else:
            klass, k = is_ext and (SubjectExtProperty, PropertyType.EXTENDED) or (SubjectProperty, PropertyType.DEFAULT)
            val = self._storage.get(klass(prop))
            # update cache if present
            if self._cached is not None:
                self._cached[k]["values"][prop] = val
                # remove prop from inserts and ensure it is in updates (ignore deletes)
                if prop in self._cached[k]["created"]:
                    self._cached[k]["created"].remove(prop)
                self._cached[k]["updated"].add(prop)
            return val

    def get(self, prop, use_cache=None):
        return self._get(prop, False, use_cache)

    def get_ext(self, prop, use_cache=None):
        return self._get(prop, True, use_cache)

    def _delete(self, prop, is_ext, is_mute, use_cache):
        if use_cache is None:
            use_cache = self._use_cache
        if use_cache:
            if self._cached is None:
                self._load()
            k = is_ext and PropertyType.EXTENDED or PropertyType.DEFAULT
            vals = self._cached[k]["values"]
            if prop not in vals:
                raise AttributeError(prop)
            del vals[prop]
            for _set in ("created", "updated"):
                if prop in self._cached[k][_set]:
                    self._cached[k][_set].remove(prop)
            self._cached[k]["deleted"].add(prop)
        else:
            klass, k = is_ext and (SubjectExtProperty, PropertyType.EXTENDED) or (SubjectProperty, PropertyType.DEFAULT)
            self._storage.delete(klass(prop))
            if self._cached is not None:
                if prop in self._cached[k]["values"]:
                    del self._cached[k]["values"][prop]
                for _set in ["created", "updated", "deleted"]:
                    if prop in self._cached[k][_set]:
                        self._cached[k][_set].remove(prop)

        if not is_mute:
            payload = {PayloadConst.PROPERTY_NAME: prop}

            from krules_core.providers import message_router_factory
            from krules_core import messages
            message_router_factory().route(messages.SUBJECT_PROPERTY_DELETED, self, payload)

    def delete(self, prop, is_mute=False, use_cache=None):
        self._delete(prop, False, is_mute, use_cache)

    def delete_ext(self, prop, use_cache=None):
        self._delete(prop, True, False, use_cache)

    # def incr(self, prop, amount=1, is_mute=False):
    #     """
    #     Works with numeric values only (starting from zero). Only for normal properties and it use the storage backend directly.
    #     """
    #     value, old_value = self._storage.set(SubjectProperty(prop), lambda x: x is None and 0 + amount or x + amount)
    #     # when cache is loaded store (silently) the old value first to correctly trigger the subject property change event
    #     if self._cached:
    #         if not is_mute:
    #             self.set(prop, old_value, True, True)
    #         self.set(prop, value, is_mute, True)
    #     # otherwise trigger event directly and do not load the cache
    #     else:
    #         if not is_mute:
    #             payload = {PayloadConst.PROPERTY_NAME: prop, PayloadConst.OLD_VALUE: old_value,
    #                        PayloadConst.VALUE: value}
    #
    #             from krules_core.providers import message_router_factory
    #             from krules_core import messages
    #             message_router_factory().route(messages.SUBJECT_PROPERTY_CHANGED, self, payload)
    #     return value, old_value
    #
    # def decr(self, prop, amount=1, is_mute=False):
    #     """
    #     Works with numeric values only (starting from zero). Only for normal properties and it use the storage backend directly.
    #     """
    #     return self.incr(prop, -amount, is_mute)

    def get_ext_props(self):
        # If we have a cache we use it, otherwise we don't load any cache
        # and we get them from the storage.
        # This is because we need all the extended properties primarily when we route events to a subject
        # and we don't care about normal properties
        if self._cached:
            return self._cached[PropertyType.EXTENDED]["values"].copy()
        return self._storage.get_ext_props()

    def event_info(self):
        return self._event_info.copy()

    def flush(self):
        self._storage.flush()
        return self

    def store(self):

        if not self._cached:
            return

        inserts, updates, deletes = [], [], []
        for _set, k1 in ((inserts, "created"), (updates, "updated"), (deletes, "deleted")):
            for k2, klass in ((PropertyType.DEFAULT, SubjectProperty), (PropertyType.EXTENDED, SubjectExtProperty)):
                for prop in self._cached[k2][k1]:
                    try:
                        _set.append(klass(prop, self._cached[k2]["values"][prop]))
                    except KeyError as ex:
                        if _set is deletes:
                            _set.append(klass(prop))
                        else:
                            raise ex

        self._storage.store(inserts=inserts, updates=updates, deletes=deletes)
        self._cached = None

    def __len__(self):

        if self._cached is None:
            self._load()
        return len(self._cached[PropertyType.DEFAULT]["values"])

    def __iter__(self):
        if self._cached is None:
            self._load()
        return iter(self._cached[PropertyType.DEFAULT]["values"])

    def __contains__(self, item):
        if self._cached is None:
            self._load()
        return item in self._cached[PropertyType.DEFAULT]["values"]

    def __getattribute__(self, item):
        try:
            return super().__getattribute__(item)
        except AttributeError as ex:
            propname = item
            is_ext = False
            is_mute = False
            try:
                if item.startswith("m_"):
                    propname = item[2:]
                    is_mute = True
                elif item.startswith("ext_"):
                    propname = item[4:]
                    is_ext = True

                value = self._get(propname, is_ext=is_ext, use_cache=False)
            except KeyError:
                raise ex
            return _SubjectPropertyProxy(self, propname, value, is_ext, is_mute)

    def __setattr__(self, item, value):

        if item in ('name',) or item.startswith("_"):
            return super().__setattr__(item, value)

        is_mute = False
        propname = item
        is_ext = False
        if item.startswith("m_"):
            is_mute = True
            propname = item[2:]
        elif item.startswith("ext_"):
            is_mute = True
            is_ext = True
            propname = item[4:]
        return self._set(propname, value, is_ext, is_mute, use_cache=False)

    def __delattr__(self, item):
        if item in ('name',) or item.startswith("_"):
            raise Exception("cannot remove {}".format(item))

        is_mute = False
        propname = item
        is_ext = False
        if item.startswith("m_"):
            is_mute = True
            propname = item[2:]
        elif item.startswith("ext_"):
            is_mute = True
            is_ext = True
            propname = item[4:]
        return self._delete(propname, is_ext, is_mute, False)


class _SubjectPropertyProxy(wrapt.ObjectProxy):
        """
        This class wraps subject properties and it is ment primarily
        to use in interactive mode.
        It also provides access to incr / decr methods of the storage backend
        """

        _subject = None
        _prop = None
        _is_ext = None
        _is_mute = None

        def __init__(self, subject, prop, value, is_ext, is_mute):
            super().__init__(value)
            self._subject = subject
            self._prop = prop
            self._is_ext = is_ext
            self._is_mute = is_mute

        def __repr__(self):
            return self.__class__.__repr__(self.__wrapped__)

        def incr(self, amount=1):
            if self._is_ext:
                raise TypeError("not supported for extended properties")
            return self._subject.set(self._prop, lambda v: v+amount, self._is_mute, False)

        def decr(self, amount=1):
            if self._is_ext:
                raise TypeError("not supported for extended properties")
            return self._subject.set(self._prop, lambda v: v-amount, self._is_mute, False)




