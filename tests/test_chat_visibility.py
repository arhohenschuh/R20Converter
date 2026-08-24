from types import SimpleNamespace

from entities.chat import ChatMessage, Roll


class FakeDatabase(object):
    def __init__(self):
        gm = SimpleNamespace(entity={"role": 4}, _id="foundry-gm")
        player = SimpleNamespace(entity={"role": 1}, _id="foundry-player")
        self._converter = SimpleNamespace(users=SimpleNamespace(entities=[gm, player]))


def message(message_type, **overrides):
    value = {
        "type": message_type,
        "content": "private result",
        "who": "Roll20",
        "playerid": "API",
        ".priority": 123,
    }
    value.update(overrides)
    return value


def test_hidden_source_gm_whisper_remains_gm_only():
    converted = ChatMessage(
        FakeDatabase(),
        "hidden-whisper",
        message("hidden", original_type="whisper", target="gm", target_name="GM"),
    ).entity

    assert converted["type"] == ChatMessage.TYPE_WHISPER
    assert converted["whisper"] == ["foundry-gm"]


def test_secret_roll_result_remains_gm_only_without_changing_rendered_type():
    converted = ChatMessage(
        FakeDatabase(),
        "secret-roll",
        message("secretrollresult", secret=True),
    ).entity

    assert converted["type"] == ChatMessage.TYPE_OOC
    assert converted["whisper"] == ["foundry-gm"]
    assert converted["content"] == "private result"


def test_ordinary_hidden_general_message_remains_public():
    converted = ChatMessage(
        FakeDatabase(),
        "hidden-general",
        message("hidden", original_type="general"),
    ).entity

    assert converted["type"] == ChatMessage.TYPE_OOC
    assert converted["whisper"] == []


def test_roll_result_uses_structured_roll_data():
    converted = ChatMessage(
        FakeDatabase(),
        "roll-result",
        message(
            "rollresult",
            content='{"total":5,"rolls":[{"type":"R","sides":20,"dice":1,"results":[{"v":5}]}]}',
            origRoll="1d20",
        ),
    ).entity

    assert converted["rolls"] == [{
        "class": "Roll",
        "options": {},
        "dice": [],
        "formula": "1d20",
        "terms": [{
            "class": "Die",
            "options": {},
            "evaluated": True,
            "number": 1,
            "faces": 20,
            "modifiers": [],
            "results": [{"result": 5, "active": True}],
        }],
        "total": 5,
        "evaluated": True,
    }]


def test_roll_result_preserves_discarded_dice_and_modifier_total():
    converted = ChatMessage(
        FakeDatabase(),
        "modified-roll-result",
        message(
            "rollresult",
            content='{"total":18,"rolls":['
                    '{"type":"R","sides":20,"dice":2,"results":[{"v":7,"d":true},{"v":15}]},'
                    '{"type":"M","expr":"+3"}]}',
            origRoll="2d20kh1+3",
        ),
    ).entity

    terms = converted["rolls"][0]["terms"]
    assert terms[0]["results"] == [
        {"result": 7, "active": False},
        {"result": 15, "active": True},
    ]
    assert terms[1:] == [
        {"class": "OperatorTerm", "options": {}, "evaluated": True, "operator": "+"},
        {"class": "NumericTerm", "options": {}, "evaluated": True, "number": 3},
    ]


def test_grouped_roll_preserves_nested_dice_and_modifier():
    converted = ChatMessage(
        FakeDatabase(),
        "grouped-roll-result",
        message(
            "rollresult",
            content='{"total":9,"rolls":[{"type":"G","rolls":[['
                    '{"type":"R","dice":2,"sides":4,"mods":{},'
                    '"results":[{"v":1},{"v":4}]},'
                    '{"type":"M","expr":"+4"}]],"mods":{},'
                    '"resultType":"sum","results":[{"v":9}]}]}',
            origRoll="{2D4+4}",
        ),
    ).entity

    pool = converted["rolls"][0]["terms"][0]
    assert pool["class"] == "PoolTerm"
    assert pool["terms"] == ["2d4+4"]
    assert pool["modifiers"] == []
    assert pool["results"] == [{"result": 9, "active": True}]
    nested = pool["rolls"][0]
    assert nested["formula"] == "2d4+4"
    assert nested["total"] == 9
    assert nested["terms"][0]["results"] == [
        {"result": 1, "active": True},
        {"result": 4, "active": True},
    ]
    assert nested["terms"][1:] == [
        {"class": "OperatorTerm", "options": {}, "evaluated": True, "operator": "+"},
        {"class": "NumericTerm", "options": {}, "evaluated": True, "number": 4},
    ]


def test_grouped_keep_high_uses_only_retained_dice_for_critical_state():
    source = {
        "total": 20,
        "rolls": [{
            "type": "G",
            "rolls": [
                [{"type": "R", "dice": 1, "sides": 20, "results": [{"v": 1}]}],
                [{"type": "R", "dice": 1, "sides": 20, "results": [{"v": 20}]}],
            ],
            "mods": {"keep": {"count": 1, "end": "h"}},
            "results": [{"v": 1, "d": True}, {"v": 20}],
        }],
    }

    roll = Roll("{1d20,1d20}kh1", source)
    pool = roll.toJSON()["terms"][0]

    assert pool["modifiers"] == ["kh1"]
    assert pool["results"] == [
        {"result": 1, "active": False},
        {"result": 20, "active": True},
    ]
    assert roll.isCrit() is True
    assert not roll.isFail()
    assert "1" in roll.getTooltip()
    assert "20" in roll.getTooltip()


def test_grouped_roll_without_nested_data_preserves_aggregate_fallback():
    converted = ChatMessage(
        FakeDatabase(),
        "legacy-grouped-roll-result",
        message(
            "rollresult",
            content='{"total":14,"rolls":[{"type":"G","results":[{"v":14}]}]}',
            origRoll="{1d20+4}",
        ),
    ).entity

    assert converted["rolls"][0]["terms"] == [{
        "class": "StringTerm",
        "options": {},
        "evaluated": True,
        "term": "{1d20+4}",
    }]
