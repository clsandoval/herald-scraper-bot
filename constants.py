HERO_ID_TO_NAME = {
    1: "antimage",
    2: "axe",
    3: "bane",
    4: "bloodseeker",
    5: "crystal_maiden",
    6: "drow_ranger",
    7: "earthshaker",
    8: "juggernaut",
    9: "mirana",
    10: "morphling",
    11: "nevermore",
    12: "phantom_lancer",
    13: "puck",
    14: "pudge",
    15: "razor",
    16: "sand_king",
    17: "storm_spirit",
    18: "sven",
    19: "tiny",
    20: "vengefulspirit",
    21: "windrunner",
    22: "zuus",
    23: "kunkka",
    25: "lina",
    26: "lion",
    27: "shadow_shaman",
    28: "slardar",
    29: "tidehunter",
    30: "witch_doctor",
    31: "lich",
    32: "riki",
    33: "enigma",
    34: "tinker",
    35: "sniper",
    36: "necrolyte",
    37: "warlock",
    38: "beastmaster",
    39: "queenofpain",
    40: "venomancer",
    41: "faceless_void",
    42: "skeleton_king",
    43: "death_prophet",
    44: "phantom_assassin",
    45: "pugna",
    46: "templar_assassin",
    47: "viper",
    48: "luna",
    49: "dragon_knight",
    50: "dazzle",
    51: "rattletrap",
    52: "leshrac",
    53: "furion",
    54: "life_stealer",
    55: "dark_seer",
    56: "clinkz",
    57: "omniknight",
    58: "enchantress",
    59: "huskar",
    60: "night_stalker",
    61: "broodmother",
    62: "bounty_hunter",
    63: "weaver",
    64: "jakiro",
    65: "batrider",
    66: "chen",
    67: "spectre",
    69: "doom_bringer",
    68: "ancient_apparition",
    70: "ursa",
    71: "spirit_breaker",
    72: "gyrocopter",
    73: "alchemist",
    74: "invoker",
    75: "silencer",
    76: "obsidian_destroyer",
    77: "lycan",
    78: "brewmaster",
    79: "shadow_demon",
    80: "lone_druid",
    81: "chaos_knight",
    82: "meepo",
    83: "treant",
    84: "ogre_magi",
    85: "undying",
    86: "rubick",
    87: "disruptor",
    88: "nyx_assassin",
    89: "naga_siren",
    90: "keeper_of_the_light",
    91: "wisp",
    92: "visage",
    93: "slark",
    94: "medusa",
    95: "troll_warlord",
    96: "centaur",
    97: "magnataur",
    98: "shredder",
    99: "bristleback",
    100: "tusk",
    101: "skywrath_mage",
    102: "abaddon",
    103: "elder_titan",
    104: "legion_commander",
    105: "techies",
    106: "ember_spirit",
    107: "earth_spirit",
    108: "abyssal_underlord",
    109: "terrorblade",
    110: "phoenix",
    111: "oracle",
    112: "winter_wyvern",
    113: "arc_warden",
    114: "monkey_king",
    119: "dark_willow",
    120: "pangolier",
    121: "grimstroke",
    123: "hoodwink",
    126: "void_spirit",
    128: "snapfire",
    129: "mars",
    135: "dawnbreaker",
    136: "marci",
    137: "primal_beast",
    138: "muerta",
    131: "ringmaster",
    145: "kez",
}
ITEM_MAP = {
    "0": "ability_base",
    "1": "blink",
    "2": "blades_of_attack",
    "3": "broadsword",
    "4": "chainmail",
    "5": "claymore",
    "6": "helm_of_iron_will",
    "7": "javelin",
    "8": "mithril_hammer",
    "9": "platemail",
    "10": "quarterstaff",
    "11": "quelling_blade",
    "12": "ring_of_protection",
    "13": "gauntlets",
    "14": "slippers",
    "15": "mantle",
    "16": "branches",
    "17": "belt_of_strength",
    "18": "boots_of_elves",
    "19": "robe",
    "20": "circlet",
    "21": "ogre_axe",
    "22": "blade_of_alacrity",
    "23": "staff_of_wizardry",
    "24": "ultimate_orb",
    "25": "gloves",
    "26": "lifesteal",
    "27": "ring_of_regen",
    "28": "sobi_mask",
    "29": "boots",
    "30": "gem",
    "31": "cloak",
    "32": "talisman_of_evasion",
    "33": "cheese",
    "34": "magic_stick",
    "35": "recipe_magic_wand",
    "36": "magic_wand",
    "37": "ghost",
    "38": "clarity",
    "39": "flask",
    "40": "dust",
    "41": "bottle",
    "42": "ward_observer",
    "43": "ward_sentry",
    "44": "tango",
    "45": "courier",
    "46": "tpscroll",
    "47": "recipe_travel_boots",
    "48": "travel_boots",
    "49": "recipe_phase_boots",
    "50": "phase_boots",
    "51": "demon_edge",
    "52": "eagle",
    "53": "reaver",
    "54": "relic",
    "55": "hyperstone",
    "56": "ring_of_health",
    "57": "void_stone",
    "58": "mystic_staff",
    "59": "energy_booster",
    "60": "point_booster",
    "61": "vitality_booster",
    "62": "recipe_power_treads",
    "63": "power_treads",
    "64": "recipe_hand_of_midas",
    "65": "hand_of_midas",
    "66": "recipe_oblivion_staff",
    "67": "oblivion_staff",
    "68": "recipe_pers",
    "69": "pers",
    "70": "recipe_poor_mans_shield",
    "71": "poor_mans_shield",
    "72": "recipe_bracer",
    "73": "bracer",
    "74": "recipe_wraith_band",
    "75": "wraith_band",
    "76": "recipe_null_talisman",
    "77": "null_talisman",
    "78": "recipe_mekansm",
    "79": "mekansm",
    "80": "recipe_vladmir",
    "81": "vladmir",
    "85": "recipe_buckler",
    "86": "buckler",
    "87": "recipe_ring_of_basilius",
    "88": "ring_of_basilius",
    "89": "recipe_pipe",
    "90": "pipe",
    "91": "recipe_urn_of_shadows",
    "92": "urn_of_shadows",
    "93": "recipe_headdress",
    "94": "headdress",
    "95": "recipe_sheepstick",
    "96": "sheepstick",
    "97": "recipe_orchid",
    "98": "orchid",
    "99": "recipe_cyclone",
    "100": "cyclone",
    "101": "recipe_force_staff",
    "102": "force_staff",
    "103": "recipe_dagon",
    "104": "dagon",
    "105": "recipe_necronomicon",
    "106": "necronomicon",
    "107": "recipe_ultimate_scepter",
    "108": "ultimate_scepter",
    "109": "recipe_refresher",
    "110": "refresher",
    "111": "recipe_assault",
    "112": "assault",
    "113": "recipe_heart",
    "114": "heart",
    "115": "recipe_black_king_bar",
    "116": "black_king_bar",
    "117": "aegis",
    "118": "recipe_shivas_guard",
    "119": "shivas_guard",
    "120": "recipe_bloodstone",
    "121": "bloodstone",
    "122": "recipe_sphere",
    "123": "sphere",
    "124": "recipe_vanguard",
    "125": "vanguard",
    "126": "recipe_blade_mail",
    "127": "blade_mail",
    "128": "recipe_soul_booster",
    "129": "soul_booster",
    "130": "recipe_hood_of_defiance",
    "131": "hood_of_defiance",
    "132": "recipe_rapier",
    "133": "rapier",
    "134": "recipe_monkey_king_bar",
    "135": "monkey_king_bar",
    "136": "recipe_radiance",
    "137": "radiance",
    "138": "recipe_butterfly",
    "139": "butterfly",
    "140": "recipe_greater_crit",
    "141": "greater_crit",
    "142": "recipe_basher",
    "143": "basher",
    "144": "recipe_bfury",
    "145": "bfury",
    "146": "recipe_manta",
    "147": "manta",
    "148": "recipe_lesser_crit",
    "149": "lesser_crit",
    "150": "recipe_armlet",
    "151": "armlet",
    "152": "invis_sword",
    "153": "recipe_sange_and_yasha",
    "154": "sange_and_yasha",
    "155": "recipe_satanic",
    "156": "satanic",
    "157": "recipe_mjollnir",
    "158": "mjollnir",
    "159": "recipe_skadi",
    "160": "skadi",
    "161": "recipe_sange",
    "162": "sange",
    "163": "recipe_helm_of_the_dominator",
    "164": "helm_of_the_dominator",
    "165": "recipe_maelstrom",
    "166": "maelstrom",
    "167": "recipe_desolator",
    "168": "desolator",
    "169": "recipe_yasha",
    "170": "yasha",
    "171": "recipe_mask_of_madness",
    "172": "mask_of_madness",
    "173": "recipe_diffusal_blade",
    "174": "diffusal_blade",
    "175": "recipe_ethereal_blade",
    "176": "ethereal_blade",
    "177": "recipe_soul_ring",
    "178": "soul_ring",
    "179": "recipe_arcane_boots",
    "180": "arcane_boots",
    "181": "orb_of_venom",
    "182": "stout_shield",
    "183": "recipe_invis_sword",
    "184": "recipe_ancient_janggo",
    "185": "ancient_janggo",
    "186": "recipe_medallion_of_courage",
    "187": "medallion_of_courage",
    "188": "smoke_of_deceit",
    "189": "recipe_veil_of_discord",
    "190": "veil_of_discord",
    "191": "recipe_necronomicon_2",
    "192": "recipe_necronomicon_3",
    "193": "necronomicon_2",
    "194": "necronomicon_3",
    "196": "diffusal_blade_2",
    "197": "recipe_dagon_2",
    "198": "recipe_dagon_3",
    "199": "recipe_dagon_4",
    "200": "recipe_dagon_5",
    "201": "dagon_2",
    "202": "dagon_3",
    "203": "dagon_4",
    "204": "dagon_5",
    "205": "recipe_rod_of_atos",
    "206": "rod_of_atos",
    "207": "recipe_abyssal_blade",
    "208": "abyssal_blade",
    "209": "recipe_heavens_halberd",
    "210": "heavens_halberd",
    "211": "recipe_ring_of_aquila",
    "212": "ring_of_aquila",
    "213": "recipe_tranquil_boots",
    "214": "tranquil_boots",
    "215": "shadow_amulet",
    "216": "enchanted_mango",
    "217": "recipe_ward_dispenser",
    "218": "ward_dispenser",
    "219": "recipe_travel_boots_2",
    "220": "travel_boots_2",
    "221": "recipe_lotus_orb",
    "222": "recipe_meteor_hammer",
    "223": "meteor_hammer",
    "224": "recipe_nullifier",
    "225": "nullifier",
    "226": "lotus_orb",
    "227": "recipe_solar_crest",
    "228": "recipe_octarine_core",
    "229": "solar_crest",
    "230": "recipe_guardian_greaves",
    "231": "guardian_greaves",
    "232": "aether_lens",
    "233": "recipe_aether_lens",
    "234": "recipe_dragon_lance",
    "235": "octarine_core",
    "236": "dragon_lance",
    "237": "faerie_fire",
    "238": "recipe_iron_talon",
    "239": "iron_talon",
    "240": "blight_stone",
    "241": "tango_single",
    "242": "crimson_guard",
    "243": "recipe_crimson_guard",
    "244": "wind_lace",
    "245": "recipe_bloodthorn",
    "246": "recipe_moon_shard",
    "247": "moon_shard",
    "248": "recipe_silver_edge",
    "249": "silver_edge",
    "250": "bloodthorn",
    "251": "recipe_echo_sabre",
    "252": "echo_sabre",
    "253": "recipe_glimmer_cape",
    "254": "glimmer_cape",
    "255": "recipe_aeon_disk",
    "256": "aeon_disk",
    "257": "tome_of_knowledge",
    "258": "recipe_kaya",
    "259": "kaya",
    "260": "refresher_shard",
    "261": "crown",
    "262": "recipe_hurricane_pike",
    "263": "hurricane_pike",
    "265": "infused_raindrop",
    "266": "recipe_spirit_vessel",
    "267": "spirit_vessel",
    "268": "recipe_holy_locket",
    "269": "holy_locket",
    "270": "recipe_ultimate_scepter_2",
    "271": "ultimate_scepter_2",
    "272": "recipe_kaya_and_sange",
    "273": "kaya_and_sange",
    "274": "recipe_yasha_and_kaya",
    "275": "recipe_trident",
    "276": "combo_breaker",
    "277": "yasha_and_kaya",
    "279": "ring_of_tarrasque",
    "286": "flying_courier",
    "287": "keen_optic",
    "288": "grove_bow",
    "289": "quickening_charm",
    "290": "philosophers_stone",
    "291": "force_boots",
    "292": "desolator_2",
    "293": "phoenix_ash",
    "294": "seer_stone",
    "295": "greater_mango",
    "297": "vampire_fangs",
    "298": "craggy_coat",
    "299": "greater_faerie_fire",
    "300": "timeless_relic",
    "301": "mirror_shield",
    "302": "elixer",
    "303": "recipe_ironwood_tree",
    "304": "ironwood_tree",
    "305": "royal_jelly",
    "306": "pupils_gift",
    "307": "tome_of_aghanim",
    "308": "repair_kit",
    "309": "mind_breaker",
    "310": "third_eye",
    "311": "spell_prism",
    "312": "horizon",
    "313": "fusion_rune",
    "317": "recipe_fallen_sky",
    "325": "princes_knife",
    "326": "spider_legs",
    "327": "helm_of_the_undying",
    "328": "mango_tree",
    "330": "witless_shako",
    "331": "vambrace",
    "334": "imp_claw",
    "335": "flicker",
    "336": "spy_gadget",
    "349": "arcane_ring",
    "354": "ocean_heart",
    "355": "broom_handle",
    "356": "trusty_shovel",
    "357": "nether_shawl",
    "358": "dragon_scale",
    "359": "essence_ring",
    "360": "clumsy_net",
    "361": "enchanted_quiver",
    "362": "ninja_gear",
    "363": "illusionsts_cape",
    "364": "havoc_hammer",
    "365": "panic_button",
    "366": "apex",
    "367": "ballista",
    "368": "woodland_striders",
    "369": "trident",
    "370": "demonicon",
    "371": "fallen_sky",
    "372": "pirate_hat",
    "373": "dimensional_doorway",
    "374": "ex_machina",
    "375": "faded_broach",
    "376": "paladin_sword",
    "377": "minotaur_horn",
    "378": "orb_of_destruction",
    "379": "the_leveller",
    "381": "titan_sliver",
    "473": "voodoo_mask",
    "485": "blitz_knuckles",
    "533": "recipe_witch_blade",
    "534": "witch_blade",
    "565": "chipped_vest",
    "566": "wizard_glass",
    "569": "orb_of_corrosion",
    "570": "gloves_of_travel",
    "571": "trickster_cloak",
    "573": "elven_tunic",
    "574": "cloak_of_flames",
    "575": "venom_gland",
    "576": "gladiator_helm",
    "577": "possessed_mask",
    "578": "ancient_perseverance",
    "582": "oakheart",
    "585": "stormcrafter",
    "588": "overflowing_elixir",
    "589": "mysterious_hat",
    "593": "fluffy_hat",
    "596": "falcon_blade",
    "597": "recipe_mage_slayer",
    "598": "mage_slayer",
    "599": "recipe_falcon_blade",
    "600": "overwhelming_blink",
    "603": "swift_blink",
    "604": "arcane_blink",
    "606": "recipe_arcane_blink",
    "607": "recipe_swift_blink",
    "608": "recipe_overwhelming_blink",
    "609": "aghanims_shard",
    "610": "wind_waker",
    "612": "recipe_wind_waker",
    "633": "recipe_helm_of_the_overlord",
    "635": "helm_of_the_overlord",
    "637": "star_mace",
    "638": "penta_edged_sword",
    "640": "recipe_orb_of_corrosion",
    "653": "recipe_grandmasters_glaive",
    "655": "grandmasters_glaive",
    "674": "warhammer",
    "675": "psychic_headband",
    "676": "ceremonial_robe",
    "677": "book_of_shadows",
    "678": "giants_ring",
    "679": "vengeances_shadow",
    "680": "bullwhip",
    "686": "quicksilver_amulet",
    "691": "recipe_eternal_shroud",
    "692": "eternal_shroud",
    "725": "aghanims_shard_roshan",
    "727": "ultimate_scepter_roshan",
    "731": "satchel",
    "824": "assassins_dagger",
    "825": "ascetic_cap",
    "826": "sample_picker",
    "827": "icarus_wings",
    "828": "misericorde",
    "829": "force_field",
    "834": "black_powder_bag",
    "835": "paintball",
    "836": "light_robes",
    "837": "heavy_blade",
    "838": "unstable_wand",
    "839": "fortitude_ring",
    "840": "pogo_stick",
    "849": "mechanical_arm",
    "907": "recipe_wraith_pact",
    "908": "wraith_pact",
    "910": "recipe_revenants_brooch",
    "911": "revenants_brooch",
    "930": "recipe_boots_of_bearing",
    "931": "boots_of_bearing",
    "938": "slime_vial",
    "939": "harpoon",
    "940": "wand_of_the_brine",
    "945": "seeds_of_serenity",
    "946": "lance_of_pursuit",
    "947": "occult_bracelet",
    "948": "tome_of_omniscience",
    "949": "ogre_seal_totem",
    "950": "defiant_shell",
    "968": "arcane_scout",
    "969": "barricade",
    "990": "eye_of_the_vizier",
    "998": "manacles_of_power",
    "1000": "bottomless_chalice",
    "1017": "wand_of_sanctitude",
    "1021": "river_painter",
    "1022": "river_painter2",
    "1023": "river_painter3",
    "1024": "river_painter4",
    "1025": "river_painter5",
    "1026": "river_painter6",
    "1027": "river_painter7",
    "1028": "mutation_tombstone",
    "1029": "super_blink",
    "1030": "pocket_tower",
    "1032": "pocket_roshan",
    "1076": "specialists_array",
    "1077": "dagger_of_ristul",
    "1090": "muertas_gun",
    "1091": "samurai_tabi",
    "1092": "recipe_hermes_sandals",
    "1093": "hermes_sandals",
    "1094": "recipe_lunar_crest",
    "1095": "lunar_crest",
    "1096": "recipe_disperser",
    "1097": "disperser",
    "1098": "recipe_samurai_tabi",
    "1099": "recipe_witches_switch",
    "1100": "witches_switch",
    "1101": "recipe_harpoon",
    "1106": "recipe_phylactery",
    "1107": "phylactery",
    "1122": "diadem",
    "1123": "blood_grenade",
    "1124": "spark_of_courage",
    "1125": "cornucopia",
    "1127": "recipe_pavise",
    "1128": "pavise",
    "1154": "royale_with_cheese",
    "1156": "ancient_guardian",
    "1157": "safety_bubble",
    "1158": "whisper_of_the_dread",
    "1159": "nemesis_curse",
    "1160": "avianas_feather",
    "1161": "unwavering_condition",
    "1162": "halo",
    "1163": "recipe_aetherial_halo",
    "1164": "aetherial_halo",
    "1167": "light_collector",
    "1168": "rattlecage",
    "1440": "black_grimoire",
    "1441": "grisgris",
    "1466": "gungir",
    "1487": "claddish_spyglass",
    "1565": "recipe_gungir",
    "1800": "recipe_caster_rapier",
    "1801": "caster_rapier",
    "1802": "tiara_of_selemene",
    "1803": "doubloon",
    "1804": "roshans_banner",
    "1805": "recipe_devastator",
    "1806": "devastator",
    "1807": "recipe_angels_demise",
    "1808": "angels_demise",
    "2091": "tier1_token",
    "2092": "tier2_token",
    "2093": "tier3_token",
    "2094": "tier4_token",
    "2095": "tier5_token",
    "2096": "vindicators_axe",
    "2097": "duelist_gloves",
    "2098": "horizons_equilibrium",
    "2099": "blighted_spirit",
    "2190": "dandelion_amulet",
    "2191": "turtle_shell",
    "2192": "martyrs_plate",
    "2193": "gossamer_cape",
    "4204": "famango",
    "4205": "great_famango",
    "4206": "greater_famango",
    "4207": "recipe_great_famango",
    "4208": "recipe_greater_famango",
    "4300": "ofrenda",
    "4301": "ofrenda_shovel",
    "4302": "ofrenda_pledge",
}


RANK_MAP = {
    11: "Herald [1]",
    12: "Herald [2]",
    13: "Herald [3]",
    14: "Herald [4]",
    15: "Herald [5]",
}
