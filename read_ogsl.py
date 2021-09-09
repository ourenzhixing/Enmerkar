﻿import sys
import re
import codecs
import unicodedata

#sys.stdout = codecs.getwriter("utf-16")(sys.stdout.detach())


MODIFIERS = {
  "g": "GUNU",
  "s": "SHESHIG",
  "t": "TENU",
  "z": "ZIDA TENU",
  "k": "KABA TENU",
  # In U+1248F CUNEIFORM SIGN DUG TIMES ASH AT LEFT, LAK561, given as
  # @uname CUNEIFORM SIGN DUG TIMES ASH FRONT in OGSL.
  "f": "AT LEFT",
  "90": "ROTATED NINETY DEGREES",
  "n": "NUTILLU",
  "180": "INVERTED",
  "v": "ASTERISK",  # In 𒋬 TA ASTERISK.
}


def compute_expected_unicode_name_at(string, index, inner_plus):
  expected_unicode_name = ""
  i = index
  while i < len(string):
    c = string[i]
    if (i + 4 <= len(string) and
        string[i:i+3] == "LAK" and
        string[i+3].isdigit()):
      lak_number = 0
      i += 3
      while i < len(string) and string[i].isdigit():
        lak_number *= 10
        lak_number += int(string[i])
        i += 1
      expected_unicode_name += "LAK-%03d" % lak_number
      continue
    i += 1
    if c == "|":
      continue
    elif c == "(":
      opened = i-1
      (inner_sign, i) = compute_expected_unicode_name_at(string, i, inner_plus)
      if (string[i-1] != ")"):
        raise ValueError(f"unmatched parenthesis in {string},\n{string}\n{(opened)*' '+'('+(i-2-opened)*'~'+string[i-1]}")
      inner_sign = inner_sign.replace(".".join(3*["DISH"]), "THREE DISH")
      inner_sign = inner_sign.replace(".".join(3*["DISH TENU"]), "THREE DISH TENU")
      # Unicode uses PLUS for . in inner signs ×., thus
      # 𒌍 U.U.U is U U U but 𒀔 AB×(U.U.U) is AB TIMES U PLUS U PLUS U,
      # 𒀙 AB₂×(ME.EN) is AB₂ TIMES ME PLUS EN.
      # TODO(egg): It’s messier than that.  Clarify.
      expected_unicode_name += (inner_sign.replace(".", " PLUS ")
                                if inner_plus else
                                inner_sign.replace(".", " "))
    elif c == ")":
      break
    elif c == "Š":
      expected_unicode_name += "SH"
    elif c in "₀₁₂₃₄₅₆₇₈₉":
      expected_unicode_name += chr(ord("0") + ord(c) - ord("₀"))
    elif c == "%":
      expected_unicode_name += " CROSSING "
    elif c == "&":
      expected_unicode_name += " OVER "
    elif c in "+":
      expected_unicode_name += "."
    elif c == "×":
      expected_unicode_name += " TIMES "
    elif c == "@":
      ahead = name[i]
      if ahead.islower() or ahead.isdigit():
        if ahead.isdigit():
          ahead = ""
          while i < len(string) and name[i].isdigit():
            ahead += name[i]
            i += 1
        else:
          i += 1
        if ahead in MODIFIERS:
          expected_unicode_name += " " + MODIFIERS[ahead]
        else:
          raise ValueError(f"Unexpected modifier @{ahead} in {name}")
      else:
        expected_unicode_name += " OPPOSING "
    else:
      expected_unicode_name += c
  expected_unicode_name = re.sub("(^|\.)3 TIMES ([^.]*)", r"\1\2 THREE TIMES", expected_unicode_name)
  expected_unicode_name = re.sub("(^|\.)4 TIMES ([^.]*)", r"\1\2 SQUARED", expected_unicode_name)
  return (expected_unicode_name, i)


def compute_expected_unicode_name(string, inner_plus=True):
  # Unicode sometimes distributes & over ., but not always.
  if string == "|(KASKAL.LAGAB×U)&(KASKAL.LAGAB×U)|":
    string = "|(KASKAL&KASKAL).(LAGAB×U&LAGAB×U)|"
  name = compute_expected_unicode_name_at(string, 0, inner_plus)[0]
  return name.replace(".", " ") if inner_plus else name.replace(".", " PLUS ")


with open(r"..\ogsl\00lib\ogsl.asl", encoding="utf-8") as f:
  lines = f.read().split("\n")

sign_name = None
form_id = None
name = None
codepoints = None
values = []

main_forms_by_name = {}
forms_by_name = {}
encoded_forms_by_value = {}

class Form:
  def __init__(self, name, form_id, sign, values, codepoints):
    self.name = name
    self.form_id = form_id
    self.sign = sign
    self.values = values
    self.codepoints = codepoints

  def __str__(self):
    return (f"{self.name} {self.codepoints} (form {self.form_id} of {self.sign})"
            if self.form_id else f"{self.name} {self.codepoints}")

  def __repr__(self):
    return str(self)

i = 0
try:
  for line in lines:
    i += 1
    if line.strip().startswith("#"):
      continue
    tokens = line.split()
    if not tokens:
      continue
    if tokens[0] == "@sign" or tokens[0] == "@form" or tokens[:2] == ["@end", "sign"]:
      if name:
        if form_id:
          form = Form(name, form_id, main_forms_by_name[sign_name], values, codepoints)
        else:
          form = Form(name, form_id, None, values, codepoints)
          if name in main_forms_by_name:
            raise ValueError(f"Duplicate signs {name}: {main_forms_by_name[name]} and {form}")
          main_forms_by_name[name] = form
        if name in forms_by_name:
          forms_by_name[name].append(form)
        else:
          forms_by_name[name] = [form]
      name = None
      codepoints = None
      values = []
    if tokens[0] == "@sign":
      if len(tokens) != 2:
        raise ValueError(tokens)
      name = tokens[-1]
      sign_name = tokens[-1]
      form_id = None
    if tokens[0] == "@form":
      if len(tokens) != 3 and not tokens[3][0] in ("x", "["):
        raise ValueError(tokens)
      name = tokens[-1]
      form_id = tokens[1]
    if tokens[0] == "@v":  # Excluding deprecated values @v-, as well as questionable @v? for now.
      if tokens[1].startswith("%") or tokens[1].startswith("#"):
        if tokens[1] in ("%akk", "%elx", "#nib", "#old", "#struck"):  # What do the # annotations mean?
          value = tokens[2]
        elif tokens[1] == "%akk/n":
          continue  # These values seem to be sumerograms in normalized Akkadian spelling, out of scope for now.
        else:
          raise ValueError(tokens)
      else:
        if len(tokens) > 2 and not tokens[2].startswith("["):
          raise ValueError(tokens)
        value = tokens[1]
      if value.startswith("/") and value.endswith("/"):
        continue  # Not sure what the values between slashes are.
      if "-" in value:
        # Not sure what those values for sign sequences, e.g., e₆-a aš₇-gi₄, etc. are about; just type the components.
        continue
      if "°" in value:  # What is up with those ° and ·?
        if value not in ("za°rahₓ", "zu°liₓ"):
          raise ValueError(value)
        continue
      if "·" in value:
        if value not in ("za·rahₓ", "zu·liₓ"):
          raise ValueError(value)
        if value == "zu·liₓ":
          # 𒆠𒆪𒊕 has zarahₓ, but 𒆉 does not have zuliₓ (reading given in epsd though, e.g. http://oracc.museum.upenn.edu/epsd2/o0025193).
          value = "zuliₓ"
        else:
          continue
      values.append(value)
    if tokens[0] == "@ucode":
      if len(tokens) != 2:
        raise ValueError(tokens)
      codepoints = ''.join('X' if x in ('X', 'None') else chr(int("0" + x, 16)) for x in tokens[-1].split("."))
      for c in codepoints:
        if ord(c) >= 0xE000 and ord(c) <= 0xF8FF:
          codepoints = None
          break
except Exception as e:
  print(f"line {i}:")
  print(line)
  print(e)
  raise

for name, forms in forms_by_name.items():
  encodings = sorted(set(form.codepoints for form in forms if form.codepoints))
  if len(encodings) > 1:
    raise ValueError(f"Differing signs for name {name}: {forms}")
  if encodings:
    encoding = encodings[0]
    for form in forms:
      form.codepoints = encoding


def rename(old_name, new_name):
  forms = forms_by_name[old_name]
  for form in forms:
    form.name = new_name
  del forms_by_name[old_name]
  forms_by_name[new_name] = forms
  if old_name in main_forms_by_name:
    del main_forms_by_name[old_name]
    main_forms_by_name[new_name] = forms

# OGSL naming bugs handled here:

# Insufficiently decomposed/normalized in OGSL.
for name in ("|DIM×EŠ|", "|KA×EŠ|", "|LAK617×MIR|", "|KAR.MUŠ|", "|ŠE₃.TU.BU|", "|GAD+KID₂.DUH|", "|ŠUL.GI|"):
  rename(name,
         name.replace(
             "EŠ", "(U.U.U)").replace(
             "MIR", "DUN3@g@g").replace(
             "KAR", "TE.A").replace(
             "ŠE₃", "EŠ₂").replace(
             "KID₂", "TAK₄").replace(
             "ŠUL", "DUN"))

# Insufficiently decomposed in its name, and also incorrectly decomposed in its encoding. see below.
rename("ŠITA₂", "|ŠITA.GIŠ|")

rename("|ŠU₂.NESAG|", "|ŠU₂.NISAG|")

# LAK207 looks to me like ŠE.HUB₂, not (ŠE&ŠE).HUB₂.
# Conventiently Unicode has the former and not the latter.
rename("|(ŠE&ŠE).HUB₂|", "|ŠE.HUB₂|")

# ASCII ugliness in form ~c |ŠU₂.3xAN| of |BAR.AN|.  OGSL correctly uses 3×AN everywhere else.
rename("|ŠU₂.3xAN|", "|ŠU₂.3×AN|")

# ED, not decomposed in its Unicode name.  Other overdecomposed signs are
# handled below, but because of the ED garbling we actually rename this one.
# TODO(egg): It has no values, imbue it with GAN? http://oracc.museum.upenn.edu/dcclt/Q000024
rename("|AŠ.GAN|", "LAK062")


# OGSL encoding bugs handled here.
for name, forms in forms_by_name.items():
  for form in forms:
    if name == "LAK212":
      form.codepoints = "𒀷"
    if name == "|A₂.ZA.AN.MUŠ₃|":
      if form.codepoints != "𒀀𒍝𒀭𒈹":
        raise ValueError("OGSL bug fixed")
      else:
        # TODO(egg): check Emar 6/2, p. 508-515 and Emar 6/2, p. 730, Msk 74209a: o i 33–36',
        # see http://oracc.museum.upenn.edu/epsd2/o0024610,
        # https://cdli.ucla.edu/search/search_results.php?SearchMode=Text&ObjectID=P271911.
        form.codepoints = "𒀉𒍝𒀭𒈹"
    if name == "|DAG.KISIM₅×GA|":
      # Off by one codepoint.
      if form.codepoints != "𒁜":
        raise ValueError("OGSL bug fixed")
      form.codepoints = "𒁛"
    if name in ("|BI.ZIZ₂|", "|BI.ZIZ₂.A.AN|", "|BI.ZIZ₂.AN|", "|BI.ZIZ₂.AN.NA|"):
      # OGSL sometimes (but not always) uses 𒀾 AŠ₂ for 𒍩 ZIZ₂).
      if "𒀾" not in form.codepoints:
        raise ValueError("OGSL bug fixed")
      form.codepoints = form.codepoints.replace("𒀾", "𒍩")
    if name == "|LU₂.SU|":
      # šimašgi is very blatantly LU₂.SU, not LU.SU.
      # https://cdli.ucla.edu/search/search_results.php?SearchMode=Text&PrimaryPublication=&MuseumNumber=&Provenience=&Period=&TextSearch=szimaszgi&ObjectID=&requestFrom=Submit
      if form.codepoints != "𒇻𒋢":
        raise ValueError("OGSL bug fixed")
      form.codepoints = "𒇽𒋢"
    if name == "|LU₂.SU.A|":
      # Same as above.
      # https://cdli.ucla.edu/search/search_results.php?SearchMode=Text&PrimaryPublication=&MuseumNumber=&Provenience=&Period=&TextSearch=szimaszgi2&ObjectID=&requestFrom=Submit
      if form.codepoints != "𒇻𒋢𒀀":
        raise ValueError("OGSL bug fixed")
      form.codepoints = "𒇽𒋢𒀀"
    if name == "|LU₃.PAP.PAP|":
      # The entry has the encoding for BARA₂.PAP.PAP (which exists as its own form).
      # See http://oracc.museum.upenn.edu/epsd2/cbd/sux/o0040424.html, see, e.g.,
      # http://oracc.museum.upenn.edu/epsd2/sux
      # https://cdli.ucla.edu/dl/lineart/P221674_l.jpg,
      # titab₂ is pretty clearly meant to be 𒈖𒉽𒉽 (especially since 𒁈𒉽𒉽 is
      # titab already).
      if form.codepoints != "𒁈𒉽𒉽":
        raise ValueError("OGSL bug fixed")
      form.codepoints = "𒈖𒉽𒉽"
    if name == "|PA.DAG.KISIM₅×GUD|":
      # DAG instead of DAG.KISIM₅×GUD.
      if form.codepoints != "𒉺𒁖":
        raise ValueError("OGSL bug fixed")
      form.codepoints = "𒉺𒁟"
    if name == "|PA.DAG.KISIM₅×KAK|":
      # DAG instead of DAG.KISIM₅×KAK.
      if form.codepoints != "𒉺𒁖":
        raise ValueError("OGSL bug fixed")
      form.codepoints = "𒉺𒁣"
    if name == "|ŠITA.GIŠ|":  # ŠITA₂ before the renaming pass above.
      # GA₂.GIŠ seems pretty clearly wrong for the OB form, see, e.g.,
      # https://cdli.ucla.edu/search/archival_view.php?ObjectID=P241971,
      # https://cdli.ucla.edu/search/archival_view.php?ObjectID=P345503.
      # Šašková goes with ŠITA.GIŠ which looks more like it.
      # In NA ŠITA = GA₂ which may explain the confusion.
      if form.codepoints != "𒂷𒄑":
        raise ValueError("OGSL bug fixed")
      form.codepoints = "𒋖𒄑"
    if name == "|BAR.3×AN|":  # Weirdly decomposing 𒀯.
      if form.codepoints != "𒁇𒀮𒀭":
        raise ValueError("OGSL bug fixed")
      form.codepoints = "𒁇𒀯"
    if name == "|ŠU₂.DUN₃@g@g@s|":
      # Missing DUN₃@g@g@s seems to just be DUN₄.
      if form.codepoints != "𒋙":
        raise ValueError("OGSL bug fixed")
      form.codepoints = "𒋙𒂈"

    # Unicode and OGSL have both  𒋲 4×TAB and 𒅄 4×(IDIM&IDIM), with the same
    # values, namely burₓ, buruₓ, gurinₓ, gurunₓ, and kurunₓ.
    # 4×TAB has an @inote field
    #   #CHECK is this the same as |4×(IDIM&IDIM)|?
    # OGSL further has 4×IDIM with the values burₓ, buruₓ, gurinₓ, gurun₅, kurunₓ,
    # which also appears as part of PAP.PAP.4×IDIM.
    # The epsd2 uses 4×TAB http://oracc.museum.upenn.edu/epsd2/o0029082, and it
    # is attested in http://oracc.iaas.upenn.edu/dcclt/nineveh/P395694.
    # The epsd2 also uses 4×IDIM,
    # http://oracc.museum.upenn.edu/epsd2/cbd/sux/o0040043.html, it is
    # attested in http://oracc.iaas.upenn.edu/dcclt/nineveh/P365399 and also in
    # http://oracc.museum.upenn.edu/dcclt/signlists/X003882.21.2#X003882.16.
    # I was unable to find usages of 4×(IDIM&IDIM) as such.
    # Šašková uses that codepoint for 4×IDIM in her Sinacherib font, see
    # http://home.zcu.cz/~ksaskova/Sign_List.html.
    # We answer the @inote in the affirmative, and consider that 4×(IDIM&IDIM)
    # is actually just 4×TAB (it has the same values, and isn’t actually used
    # anyway).  We further follow usage established by Šašková and repurpose
    # that codepoint as 4×IDIM.
    # TODO(egg): ask Tinney whether that makes sense, and if it does, write a
    # proposal to add IDIM SQUARED as an alias for IDIM OVER IDIM SQUARED and to
    # change the reference glyph.
    if name == "|4×(IDIM&IDIM)|":
      form.codepoints = None
    elif name == "|4×IDIM|":
      form.codepoints = "𒅄"
    elif name == "|PAP.PAP.4×IDIM|":
      form.codepoints = form.codepoints.replace("X", "𒅄")


    # Signs that are not really there, one way or another.
    if name == "|DAG.KISIM₅×X|" or name == "|NUNUZ.AB₂×X|":
      form.codepoints = None  # If it has an X it is not encoded.
    if name == "|IM.IM.KAD₃IM.KAD₃A|":
      # What is that supposed to be? |IM.IM.KAD₃.IM.KAD₃A|?
      # In any case they have IM.A there…
      form.codepoints = None
    if name == "|LU₂@g.UŠ₂|":
      # No LU₂ gunû…
      form.codepoints = None
    if name == "|PAP.PAP×ŠE|":
      # No PAP×ŠE afaict?
      form.codepoints = None
    if name == "|SU.RU×KUR|":
      # RU×KUR removed in https://www.unicode.org/wg2/docs/n2786.pdf.
      # The @ucode for that sign only has SU, and SU.KUR.RU exists so a font
      # could ligature it.
      form.codepoints = None

    # Unicode 7.0 fanciness.
    if name == "GIG":
      form.codepoints = "𒍼"
    if "GIG" in name and form.codepoints and "X" in form.codepoints:
      form.codepoints = form.codepoints.replace("X", "𒍼")

    if name == "|GA₂×ZIZ₂|" or form.codepoints and any(ord(sign) >= 0x12480 for sign in form.codepoints):
      # The Early Dynastic block is garbled in OGSL.
      if name == "|ŠE&ŠE.NI|":
        form.codepoints = chr(0x12532) + "𒉌"
      elif name == "|MI.ZA₇|":
        form.codepoints = "𒈪" + chr(0x12541)
      elif name == "|MUŠ₃.ZA₇|":
        form.codepoints = "𒈹" + chr(0x12541)
      elif name == "|ŠE&ŠE.KIN|":
        form.codepoints = chr(0x12532) + "𒆥"
      elif name in ("|KA×ŠE@f|", "|KUŠU₂×SAL|", "LAK20", "|SAG×TAK₄@f|", "|SAR×ŠE|",
                    "|ŠE@v+NAM₂|", "URU@g"):
        # Seemingly unencoded, |KUŠU₂×SAL| is present an early proposal,
        # http://unicode.org/wg2/docs/n4179.pdf.
        form.codepoints = None
      else:
        # For some reason Unicode has unpredictable rules for PLUS in the ED block.
        try:
          form.codepoints = unicodedata.lookup(
              "CUNEIFORM SIGN " + compute_expected_unicode_name(name, inner_plus=False))
        except KeyError:
          form.codepoints = unicodedata.lookup(
              "CUNEIFORM SIGN " + compute_expected_unicode_name(name, inner_plus=True))


# Assign encodings from components.
for name, forms in forms_by_name.items():
  if name.startswith("|") and name.endswith("|") and not forms[0].codepoints:
    encoding = ""
    components = []
    for component in re.findall(r"(?:[^.()]|\([^()]+\))+", name[1:-1]):
      if "×" in component:
        component = f"{component}"
      if component in forms_by_name and forms_by_name[component][0].codepoints:
        encoding += forms_by_name[component][0].codepoints
        components.append(component)
      else:
        break
    else:
      for form in forms:
        form.codepoints = encoding
      print(f"Encoding {forms[0] if len(forms) == 1 else forms} from {components}")


for name, forms in forms_by_name.items():
  encoding = forms[0].codepoints
  if not encoding:
    continue

  if name == "ASAL₂~a":
    # Very weird entry and very weird Unicode name.  Merging with LAK 212,
    # see above.
    continue

  if name == "|LAGAB×(IM.IM.ŠU₂LU)|":
    # Very explicitly mapped to CUNEIFORM SIGN LAGAB TIMES IM PLUS LU.
    # |LAGAB×(IM.LU)| exists as a variant of elamkuš₂ but is given no readings.
    # This one has elamkušₓ, which seems appropriate.
    continue

  if name == "|LAGAB×AŠ@t|":
    # The unicode name is LAGAB×LIŠ, which is variant ~a of this one.
    # Both are given the reading gigir₃.  Shrug.
    continue

  if name== "OO":
    continue

  expected_unicode_name = compute_expected_unicode_name(name)

  # Misnaming in Unicode? U+12036 ARKAB 𒀶 is (looking at the reference
  # glyph) LAK296, to which OGSL gives the value arkab₂, arkab being
  # GAR.IB 𒃻𒅁.
  expected_unicode_name = expected_unicode_name.replace("ARKAB2", "ARKAB")

  # OGSL decomposes 𒍧 and 𒍦, Unicode does not (perhaps for length reasons?).
  if expected_unicode_name == " OVER ".join(4 * ["ASH KABA TENU"]):
    expected_unicode_name = "ZIB KABA TENU"
  if expected_unicode_name == " OVER ".join(4 * ["ASH ZIDA TENU"]):
    expected_unicode_name = "ZIB"

  if expected_unicode_name == "BURU5":
    # Quoth the OGSL: @note The NB source for Ea II (LKU 1) describes BURU₅ as NAM nutillû.
    expected_unicode_name = "NAM NUTILLU"

  if expected_unicode_name == "ELLES396":
    # The unicode name is a value here rather than the catalogue number.
    expected_unicode_name = "ZAMX"

  # OGSL never decomposes LAL₂, so lets’ treat this as intentional.
  expected_unicode_name = expected_unicode_name.replace("LAL2", "LAL TIMES LAL")

  if expected_unicode_name == "KU4~a":
    expected_unicode_name = "KU4 VARIANT FORM"

  if expected_unicode_name == "LAGAB TIMES SHITA TENU PLUS GISH":
    expected_unicode_name = "LAGAB TIMES SHITA PLUS GISH TENU"

  # The reference glyph is more over than plus…
  if expected_unicode_name == "LAGAB TIMES GUD OVER GUD":
    expected_unicode_name = "LAGAB TIMES GUD PLUS GUD"
  if expected_unicode_name == "PA LAGAB TIMES GUD OVER GUD":
    expected_unicode_name = "PA LAGAB TIMES GUD PLUS GUD"

  # OGSL has no MA×TAK₄, Unicode has no MA GUNU TIMES TAK4.
  # This is probably fine, though I don’t know where the gunû went.
  if expected_unicode_name == "MA GUNU TIMES TAK4":
    expected_unicode_name = "MA TIMES TAK4"

  if expected_unicode_name == "MURUB4":
    # @note MURUB₄(LAK157) merges with NISAG(LAK159)
    expected_unicode_name = "NISAG"

  # Aliases from https://www.unicode.org/wg2/docs/n4277.pdf.
  # Looking up by alias work, but the name is the name, and there is no API to
  # get the alias...
  if expected_unicode_name == "NU11 TENU":
    expected_unicode_name = "SHIR TENU"
  elif expected_unicode_name == "NU11 OVER NU11 BUR OVER BUR":
    expected_unicode_name = "SHIR OVER SHIR BUR OVER BUR"

  # See the discussion above.  Maybe someday this will be an alias...
  if "IDIM SQUARED" in expected_unicode_name:
    expected_unicode_name = expected_unicode_name.replace("IDIM SQUARED", "IDIM OVER IDIM SQUARED")

  if expected_unicode_name == "SHE NUN OVER NUN":  # Not decomposed in Unicode.
    expected_unicode_name = "TIR"
  if "SHE PLUS NUN OVER NUN" in expected_unicode_name:
    expected_unicode_name = expected_unicode_name.replace("SHE PLUS NUN OVER NUN", "TIR")

  # Sometimes (but not always) decomposed in OGSL, not decomposed in Unicode.
  if expected_unicode_name == "SHU2 DUN3 GUNU GUNU SHESHIG":
    expected_unicode_name = "SHU2 DUN4"


  actual_unicode_name = " ".join(unicodedata.name(c).replace("CUNEIFORM SIGN ", "") if ord(c) >= 0x12000 else c for c in encoding)
  if "CUNEIFORM NUMERIC SIGN" in actual_unicode_name:
    continue  # TODO(egg): deal with that.

  if expected_unicode_name == "SHU OVER SHU INVERTED":  # Magical Unicode word order.
    expected_unicode_name = "SHU OVER INVERTED SHU"

  # TODO(egg): Figure out the PLUS dance someday...
  if actual_unicode_name.replace(" PLUS ", " ") != expected_unicode_name.replace(" PLUS ", " "):
    raise ValueError(f"{name} encoded as {encoding}, {expected_unicode_name} != {actual_unicode_name}")

for name, forms in forms_by_name.items():
  encoding = forms[0].codepoints
  if encoding:
    for form in forms:
      for value in form.values:
        if not value in encoded_forms_by_value:
          encoded_forms_by_value[value] = {}
        if encoding not in encoded_forms_by_value[value]:
          encoded_forms_by_value[value][encoding] = []
        encoded_forms_by_value[value][encoding].append(form)

for name, forms in forms_by_name.items():
  values = [value for form in forms for value in form.values if "@c" not in value]
  if values and not forms[0].codepoints:
    print(f"No encoding for {name} with values {values}")

for value, forms_by_codepoints in encoded_forms_by_value.items():
  if "ₓ" not in value and len(forms_by_codepoints) > 1:
    print(f"Multiple signs with value {value}: {'; '.join(forms_by_codepoints.keys())}")
    print(forms_by_codepoints.values())

for value, forms_by_codepoints in encoded_forms_by_value.items():
  if value[0] in '1234567890':
    continue  # We do numbers separately.
  for c in value:
    if c not in 'bdgptkʾṭqzšsṣhmnrlwyjaeiu₁₂₃₄₅₆₇₈₉₀ₓŋ:⁺⁻ś':  # Oracc uses ḫ for h.
      print(f"Unexpected character {c} in value {value} for {'; '.join(forms_by_codepoints.keys())}")
      print(forms_by_codepoints.values())
      break

encoded_signs = set(form.codepoints for forms in forms_by_name.values() for form in forms)
encoded_signs_with_values = set(form.codepoints for forms in forms_by_name.values() for form in forms if form.values)

for u in range(0x12000, 0x12550):  # Cuneiform, Cuneiform numbers and punctuation, Early Dynastic cuneiform.
  if unicodedata.category(chr(u)) == "Cn":
    continue
  if chr(u) not in encoded_signs:
    print(f"No form U+{u:X} {unicodedata.name(chr(u))} {chr(u)}")
  if chr(u) not in encoded_signs_with_values:
    print(f"No values for U+{u:X} {unicodedata.name(chr(u))} {chr(u)}")