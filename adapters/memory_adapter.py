"""
Adapter that hooks memory into an agent loop.
Example usage (pseudocode):
  buffer = RollingBuffer()
  episodic = EpisodicStore()
  semantic = SemanticStore()
  # on each incoming event:
  evt = {'text':..., 'patient_id':...}
  decision = decide_routing(evt)
  if decision['action'] == 'promote':
      episodic.append(evt)
  elif decision['action'] == 'ephemeral':
      pass
  else:
      pass
  # when making LLM call:
  context = buffer.get_context() + semantic.list()

"""
from memory.buffer import RollingBuffer
from memory.episodic_store import EpisodicStore
from memory.semantic_store import SemanticStore
from memory.routing import decide_routing

class MemoryAdapter:
    def __init__(self):
        self.buffer = RollingBuffer()
        self.episodic = EpisodicStore()
        self.semantic = SemanticStore()

    def ingest_event(self, event):
        self.buffer.append(event)
        decision = decide_routing(event)
        if decision['action'] == 'promote':
            self.episodic.append(event)
        # ephemeral or drop: do nothing
        return decision

    def get_context(self):
        # return combined context (buffer + semantic canonical facts)
        ctx = self.buffer.get_context()
        ctx += [{'type':'semantic','text': e['canonical_fact']} for e in self.semantic.list()]
        return ctx
