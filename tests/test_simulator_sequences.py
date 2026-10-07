"""Seeded interaction journeys through real callbacks, with no Discord connection."""
import random

import pytest

from herald import board, render
from herald.simulator import Simulator


def controls(components):
    for component in components:
        if component.get('custom_id') and not component.get('disabled'):
            yield component
        yield from controls(component.get('components', []))


@pytest.mark.parametrize('seed', [17, 613, 2026])
async def test_long_repeated_menu_journey(tmp_path, monkeypatch, seed):
    monkeypatch.setattr(board, 'DB_PATH', board.DB_PATH)
    monkeypatch.setattr(render, '_emoji', {})
    monkeypatch.setattr(board, '_thumb_cache', board.OrderedDict())
    sim = Simulator(tmp_path)
    rng = random.Random(seed)
    snapshot = await sim.request({'action': 'reset', 'scenario': 'missing-icons'})
    for step in range(60):
        if step and step % 15 == 0:
            snapshot = await sim.request({'action': 'reset', 'scenario': rng.choice(
                ['empty', 'missing-icons', 'long-text', 'pruned'])})
        available = list(controls(snapshot['components']))
        assert available
        control = rng.choice(available)
        request = {'action': 'component', 'revision': snapshot['revision'],
                   'custom_id': control['custom_id']}
        if control['type'] == 3:
            options = [option['value'] for option in control['options']]
            low, high = control.get('min_values', 1), control.get('max_values', 1)
            request['values'] = rng.sample(options, rng.randint(low, min(high, 3)))
        snapshot = await sim.request(request)
        if snapshot.get('modal'):
            values = {}
            if step % 3 == 0:
                values[sim.modal.dur.custom_id] = '>70'
            elif step % 3 == 1:
                values[sim.modal.heroes.custom_id] = 'axe'
            snapshot = await sim.request({'action': 'modal', 'revision': snapshot['revision'],
                                          'values': values})
        assert snapshot['budget']['components'] <= 40
        assert snapshot['budget']['text'] <= 4000
        assert snapshot['state']['page'] >= 0
        assert snapshot['state']['dir'] in ('ASC', 'DESC')
        assert set(snapshot['state']['sort']) <= set(board.SORTS)
        assert set(snapshot['state']['filters']) <= set(board.FILTERS)
        assert not snapshot.get('error'), (seed, step, request)
