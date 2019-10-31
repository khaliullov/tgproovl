import pickle
from collections import defaultdict
from copy import deepcopy

from telegram.ext import PicklePersistence


class ExtendedPersistence(PicklePersistence):

    def __init__(self, filename, store_user_data=True, store_chat_data=True,
                 single_file=True, on_flush=False, store_state=True):
        super(ExtendedPersistence, self).__init__(filename, store_user_data,
                                                  store_chat_data, single_file,
                                                  on_flush)
        self.state = None
        self.store_state = store_state

    def load_singlefile(self):
        try:
            filename = self.filename
            with open(self.filename, "rb") as f:
                all = pickle.load(f)
                self.user_data = defaultdict(dict, all['user_data'])
                self.chat_data = defaultdict(dict, all['chat_data'])
                self.conversations = all['conversations']
                self.state = defaultdict(dict, all['state'])
        except IOError:
            self.conversations = {}
            self.user_data = defaultdict(dict)
            self.chat_data = defaultdict(dict)
            self.state = defaultdict(dict)
        except pickle.UnpicklingError:
            raise TypeError("File {} does not contain valid pickle data".format(filename))
        except Exception:
            raise TypeError("Something went wrong unpickling {}".format(filename))

    def dump_singlefile(self):
        with open(self.filename, "wb") as f:
            all = {'conversations': self.conversations,
                   'user_data': {k: v for k, v in self.user_data.items() if len(v)},
                   'chat_data': {k: v for k, v in self.chat_data.items() if len(v)},
                   'state': self.state}
            pickle.dump(all, f)

    def get_state(self):
        if self.state:
            pass
        elif not self.single_file:
            filename = "{}_state".format(self.filename)
            data = self.load_file(filename)
            if not data:
                data = defaultdict(dict)
            else:
                data = defaultdict(dict, data)
            self.state = data
        else:
            self.load_singlefile()
        return deepcopy(self.state)

    def update_state(self, data):
        self.state = deepcopy(data)
        self.save_state()

    def save_state(self):
        if not self.on_flush:
            if not self.single_file:
                filename = "{}_state".format(self.filename)
                self.dump_file(filename, self.chat_data)
            else:
                self.dump_singlefile()

    def flush(self):
        if self.single_file:
            if self.user_data or self.chat_data or self.conversations:
                self.dump_singlefile()
        else:
            if self.user_data:
                self.dump_file("{}_user_data".format(self.filename),
                               {k: v for k, v in self.user_data.items() if len(v)})
            if self.chat_data:
                self.dump_file("{}_chat_data".format(self.filename),
                               {k: v for k, v in self.chat_data.items() if len(v)})
            if self.conversations:
                self.dump_file("{}_conversations".format(self.filename), self.conversations)
            if self.state:
                self.dump_file("{}_state".format(self.filename), self.state)
