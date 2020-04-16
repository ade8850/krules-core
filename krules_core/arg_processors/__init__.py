# Copyright 2019 The KRules Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import inspect
import jsonpath_rw_ext as jp

processors = []


class SimpleCallableArgProcessor:

    @staticmethod
    def interested_in(arg):
        try:
            sig = inspect.signature(arg)
            return len(sig.parameters) == 0
        except TypeError:
            return False

    @staticmethod
    def process(_, arg):
        return arg()


processors.append(SimpleCallableArgProcessor)


class CallableWithSelf:

    @staticmethod
    def interested_in(arg):
        try:
            sig = inspect.signature(arg)
            return len(sig.parameters) == 1 and "self" in sig.parameters
        except TypeError:
            return False

    @staticmethod
    def process(instance, arg):
        return arg(instance)


processors.append(CallableWithSelf)


class CallableWithPayload:

    @staticmethod
    def interested_in(arg):
        try:
            sig = inspect.signature(arg)
            return len(sig.parameters) == 1 and "payload" in sig.parameters
        except TypeError:
            return False

    @staticmethod
    def process(instance, arg):
        return arg(instance.payload)


#processors.append(CallableWithPayload)


class CallableWithSubject:

    @staticmethod
    def interested_in(arg):
        try:
            sig = inspect.signature(arg)
            return len(sig.parameters) == 1 and "subject" in sig.parameters
        except TypeError:
            return False

    @staticmethod
    def process(instance, arg):
        return arg(instance.subject)


#processors.append(CallableWithSubject)


class JPPayloadMatchBase:

    def __init__(self, expr):
        self._expr = expr

    @classmethod
    def interested_in(cls, arg):
        return isinstance(arg, cls)


class JPPayloadMatch(JPPayloadMatchBase):

    @staticmethod
    def process(instance, arg):
        return jp.match(arg._expr, instance.payload)


class JPPayloadMatchOne(JPPayloadMatchBase):

    @staticmethod
    def process(instance, arg):
        return jp.match1(arg._expr, instance.payload)


# processors.extend((jp_match, jp_match1))
