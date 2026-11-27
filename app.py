import streamlit as st
import pandas as pd
import os
from datetime import datetime, time, date


def force_rerun():
    """Startet die App neu, egal welche Streamlit-Version läuft."""
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    else:
        st.write("Bitte Seite manuell neu laden (F5).")


st.set_page_config(
    page_title="Skolary Classic",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

FILE_GRADES = "daten_noten.csv"
FILE_ATTENDANCE = "daten_fehlzeiten.csv"
LOGO_FILE = "logo.png"

PAUSEN = [(9, 20, 9, 40), (11, 10, 11, 40), (13, 10, 13, 20)]

DEFAULT_SUBJECTS = {
    "BWR": True,
    "InWi": True,
    "MAT": True,
    "DEU": True,
    "ENG": True,
    "VWL": True,
    "BOPM": True,
    "SPO": False,
}

GRADE_SCALE = [
    (94, 1.0),
    (90, 1.3),
    (86, 1.7),
    (79, 2.0),
    (75, 2.3),
    (71, 2.7),
    (64, 3.0),
    (60, 3.3),
    (56, 3.7),
    (49, 4.0),
    (45, 4.3),
    (41, 4.7),
    (34, 5.0),
    (30, 5.3),
    (0, 6.0),
]

TENDENZ_MAPPING = {
    "1+": 0.7,
    "1": 1.0,
    "1-": 1.3,
    "2+": 1.7,
    "2": 2.0,
    "2-": 2.3,
    "3+": 2.7,
    "3": 3.0,
    "3-": 3.3,
    "4+": 3.7,
    "4": 4.0,
    "4-": 4.3,
    "5+": 4.7,
    "5": 5.0,
    "5-": 5.3,
    "6": 6.0,
}


def determine_current_semester():
    return ".2" if 2 <= date.today().month <= 7 else ".1"


def parse_percentage_or_grade(value):
    if not value:
        return None
    val_str = str(value).strip().replace(" ", "")
    if val_str in TENDENZ_MAPPING:
        return TENDENZ_MAPPING[val_str]
    try:
        clean_num = val_str.replace(",", ".")
        number = float(clean_num)
        if number <= 6.0:
            return number
        for threshold, grade in GRADE_SCALE:
            if number >= threshold:
                return grade
        return 6.0
    except ValueError:
        return None


def parse_time_input(time_str):
    if not time_str:
        return None
    clean = time_str.strip().replace(":", "").replace(".", "")
    try:
        h, m = 0, 0
        if len(clean) in [3, 4] and clean.isdigit():
            h = int(clean[:-2])
            m = int(clean[-2:])
        elif len(clean) <= 2 and clean.isdigit():
            h = int(clean)
            m = 0
        else:
            t = datetime.strptime(time_str, "%H:%M").time()
            h, m = t.hour, t.minute
        if 0 <= h < 24 and 0 <= m < 60:
            return time(h, m)
        return None
    except:
        return None


def calculate_net_minutes(start_time, end_time):
    s_min = start_time.hour * 60 + start_time.minute
    e_min = end_time.hour * 60 + end_time.minute
    if e_min <= s_min:
        return 0
    duration = e_min - s_min
    deduction = 0
    for p_h1, p_m1, p_h2, p_m2 in PAUSEN:
        p_s, p_e = p_h1 * 60 + p_m1, p_h2 * 60 + p_m2
        ov_s, ov_e = max(s_min, p_s), min(e_min, p_e)
        if ov_s < ov_e:
            deduction += ov_e - ov_s
    return max(0, duration - deduction)


def load_data(file, cols):
    if os.path.exists(file):
        try:
            df = pd.read_csv(file)

            text_cols = ["Kommentar", "Eingabe", "Fach", "Typ", "Halbjahr", "Grund"]
            for c in text_cols:
                if c in df.columns:
                    df[c] = df[c].fillna("").astype(str)

            if "Datum" in df.columns:
                df["Datum"] = pd.to_datetime(df["Datum"], errors="coerce")

            if "Note" in df.columns:
                df["Note"] = pd.to_numeric(df["Note"], errors="coerce")

            if "Entschuldigt" in df.columns:
                df["Entschuldigt"] = (
                    df["Entschuldigt"]
                    .astype(str)
                    .str.lower()
                    .isin(["true", "1", "wahr", "yes", "1.0"])
                )

            return df

        except Exception as e:
            print(f"Fehler beim Laden von {file}: {e}")
            return pd.DataFrame(columns=cols)

    return pd.DataFrame(columns=cols)


def save_data(df, file):
    try:
        out = df.copy()
        if "Datum" in out.columns:
            out["Datum"] = pd.to_datetime(out["Datum"], errors="coerce").dt.strftime(
                "%Y-%m-%d %H:%M"
            )

        out.to_csv(file, index=False)
    except Exception as e:
        st.error(f"Fehler beim Speichern: {e}")


def get_active_subjects(df_grades):
    config = DEFAULT_SUBJECTS.copy()
    if not df_grades.empty:
        found = df_grades["Fach"].dropna().unique().tolist()
        for sub in found:
            if sub and str(sub).strip() != "" and sub not in config:
                has_exam = not df_grades[
                    (df_grades["Fach"] == sub) & (df_grades["Typ"] == "Klausur")
                ].empty
                config[sub] = has_exam
    return config


def calc_stats(df, subjects_config, selected_hj):
    results = []
    df_hj = df[df["Halbjahr"] == selected_hj]

    for fach, is_written in subjects_config.items():
        sub_df = df_hj[df_hj["Fach"] == fach]
        val, txt = None, "-"

        if not sub_df.empty:
            manual = sub_df[sub_df["Typ"] == "Zeugnisnote (Fest)"]
            if not manual.empty:
                val = manual.iloc[-1]["Note"]
                txt = f"{val:.0f} (Zeugnis)"
            else:
                klausuren = sub_df[sub_df["Typ"] == "Klausur"]["Note"].dropna()

                somi_df = sub_df[~sub_df["Typ"].isin(["Klausur", "Zeugnisnote (Fest)"])]
                sonstige = somi_df["Note"].dropna()

                if is_written:
                    if not klausuren.empty and not sonstige.empty:
                        val = (klausuren.mean() + sonstige.mean()) / 2
                    elif not klausuren.empty:
                        val = klausuren.mean()
                    elif not sonstige.empty:
                        val = sonstige.mean()
                else:
                    all_grades = sub_df["Note"].dropna()
                    if not all_grades.empty:
                        val = all_grades.mean()

                if val is not None:
                    txt = f"{val:.2f}"

        if val is not None:
            art_text = "Schriftlich" if is_written else "Mündlich"
            results.append({"Fach": fach, "Art": art_text, "Note": txt, "Wert": val})

    return pd.DataFrame(results)


if "new_subject_trigger" not in st.session_state:
    st.session_state.new_subject_trigger = None

df_grades = load_data(
    FILE_GRADES, ["Datum", "Halbjahr", "Fach", "Typ", "Eingabe", "Note", "Kommentar"]
)
df_attendance = load_data(
    FILE_ATTENDANCE,
    ["Datum", "Halbjahr", "Start", "Ende", "Minuten", "Entschuldigt", "Grund"],
)
subjects_config = get_active_subjects(df_grades)

curr_sem = determine_current_semester()
all_hjs = ["11.1", "11.2", "12.1", "12.2", "13.1", "13.2"]
def_hj_idx = next((i for i, h in enumerate(all_hjs) if h.endswith(curr_sem)), 0)

with st.sidebar:
    if os.path.exists(LOGO_FILE):
        st.image(LOGO_FILE, width=100)
    else:
        st.header("🎓")
    st.title("Skolary Classic")
    st.divider()

    st.subheader("Daten sichern/exportieren")

    csv_grades = ""
    disabled_grades = True
    if not df_grades.empty:
        df_exp_g = df_grades.copy()
        if "Datum" in df_exp_g.columns:
            df_exp_g["Datum"] = pd.to_datetime(
                df_exp_g["Datum"], errors="coerce"
            ).dt.strftime("%Y-%m-%d %H:%M")

        csv_grades = df_exp_g.to_csv(index=False).encode("utf-8")
        disabled_grades = False

    st.download_button(
        "📄 Noten (CSV)", csv_grades, "noten.csv", "text/csv", disabled=disabled_grades
    )

    csv_att = ""
    disabled_att = True
    if not df_attendance.empty:
        df_exp_a = df_attendance.copy()
        if "Datum" in df_exp_a.columns:
            df_exp_a["Datum"] = pd.to_datetime(
                df_exp_a["Datum"], errors="coerce"
            ).dt.strftime("%Y-%m-%d")

        csv_att = df_exp_a.to_csv(index=False).encode("utf-8")
        disabled_att = False

    st.download_button(
        "⏰ Fehlzeiten (CSV)",
        csv_att,
        "fehlzeiten.csv",
        "text/csv",
        disabled=disabled_att,
    )

    st.divider()
    st.markdown("**Created by Julian Schmitz**")
    st.caption("v10.1.3 | 'Death of my Sanity' Edition")

st.title("Noten & Fehlzeiten")

tab1, tab2, tab3, tab4 = st.tabs(
    ["📝 Notenliste", "⏰ Fehlzeiten", "📊 Zeugnis", "🛠️ Fächer"]
)

with tab1:
    c_form, c_list = st.columns([1, 2])
    with c_form:
        st.subheader("Eintragen")
        with st.form("grade_entry", clear_on_submit=True):
            sel_hj = st.selectbox(
                "Halbjahr", all_hjs, index=None, placeholder="Wählen..."
            )
            sel_fach = st.selectbox(
                "Fach",
                sorted(list(subjects_config.keys())),
                index=None,
                placeholder="Wählen...",
            )
            sel_typ = st.selectbox(
                "Art",
                ["Mündlich", "Test", "Klausur", "Zeugnisnote (Fest)"],
                index=None,
                placeholder="Wählen...",
            )
            inp_val = st.text_input("Note / Prozent", help="z.B. '2+' oder '85'")
            inp_kom = st.text_input("Kommentar (optional)")

            if st.form_submit_button("Speichern"):
                if sel_hj and sel_fach and sel_typ and inp_val:
                    calc = parse_percentage_or_grade(inp_val)
                    if calc is not None:
                        new_row = {
                            "Datum": datetime.now(),
                            "Halbjahr": sel_hj,
                            "Fach": sel_fach,
                            "Typ": sel_typ,
                            "Eingabe": inp_val,
                            "Note": calc,
                            "Kommentar": inp_kom if inp_kom else "",
                        }
                        df_new = pd.DataFrame([new_row])
                        df_new["Datum"] = pd.to_datetime(df_new["Datum"])
                        df_grades = pd.concat([df_grades, df_new], ignore_index=True)
                        save_data(df_grades, FILE_GRADES)
                        st.success(f"Note {calc} gespeichert!")
                        force_rerun()
                    else:
                        st.error("Format nicht erkannt.")
                else:
                    st.error("Pflichtfelder fehlen.")

with c_list:
    st.subheader("Übersicht")

    view_df = (
        df_grades[df_grades["Halbjahr"] != "System"]
        .sort_values(by=["Datum", "Fach"], ascending=[False, True])
        .reset_index(drop=True)
    )

    if not view_df.empty:
        edited_df = st.data_editor(
            view_df,
            num_rows="dynamic",
            column_config={
                "Datum": st.column_config.DatetimeColumn(
                    "Zeitpunkt", format="DD.MM.YYYY HH:mm", required=True
                ),
                "Typ": st.column_config.TextColumn("Typ", width="medium"),
                "Kommentar": st.column_config.TextColumn("Kommentar", width="medium"),
                "Note": st.column_config.NumberColumn(
                    "Note", format="%.2f", disabled=True
                ),
                "Fach": st.column_config.TextColumn("Fach", width="small"),
                "Halbjahr": st.column_config.TextColumn("Halbjahr", width="small"),
                "Eingabe": st.column_config.TextColumn("Eingabe", width="small"),
            },
            width="stretch",
            key="editor_grades",
            hide_index=True,
        )

        if not edited_df.equals(view_df):
            if "Kommentar" in edited_df.columns:
                edited_df["Kommentar"] = edited_df["Kommentar"].fillna("").astype(str)

            edited_df["Note"] = edited_df["Eingabe"].apply(parse_percentage_or_grade)

            system_rows = df_grades[df_grades["Halbjahr"] == "System"]
            final_df = pd.concat([edited_df, system_rows], ignore_index=True)

            save_data(final_df, FILE_GRADES)
            st.toast("Gespeichert!", icon="💾")
            force_rerun()
    else:
        st.info("Keine Noten eingetragen.")

with tab2:
    c1, c2 = st.columns([1, 2])

    with c1:
        st.subheader("Melden")
        with st.form("att_entry", clear_on_submit=True):
            f_hj = st.selectbox(
                "Halbjahr", all_hjs, index=None, placeholder="Wählen..."
            )
            f_date = st.date_input("Datum")
            ct1, ct2 = st.columns(2)
            t_start_s = ct1.text_input("Von", placeholder="0800", max_chars=5)
            t_end_s = ct2.text_input("Bis", placeholder="1310", max_chars=5)
            f_gr = st.text_input("Grund")
            f_ok = st.checkbox("Entschuldigt?")

            if st.form_submit_button("Eintragen"):
                ts, te = parse_time_input(t_start_s), parse_time_input(t_end_s)
                if ts and te and f_hj:
                    mins = calculate_net_minutes(ts, te)

                    new_att = {
                        "Datum": pd.to_datetime(f_date),
                        "Halbjahr": f_hj,
                        "Start": ts.strftime("%H:%M"),
                        "Ende": te.strftime("%H:%M"),
                        "Minuten": mins,
                        "Entschuldigt": f_ok,
                        "Grund": f_gr if f_gr else "",
                    }
                    df_att_new = pd.DataFrame([new_att])
                    df_attendance = pd.concat(
                        [df_attendance, df_att_new], ignore_index=True
                    )
                    save_data(df_attendance, FILE_ATTENDANCE)
                    st.success(f"Gespeichert: {mins} Netto-Minuten.")
                    force_rerun()
                else:
                    st.error("Zeitformat prüfen (HHMM).")

with c2:
    st.subheader("Liste")
    if not df_attendance.empty:
        df_attendance["Datum"] = pd.to_datetime(
            df_attendance["Datum"], dayfirst=True, errors="coerce"
        )

        view_att = df_attendance.sort_values(by="Datum", ascending=False).reset_index(
            drop=True
        )

        view_att["Schulstunden"] = view_att["Minuten"] / 45

        edited_att = st.data_editor(
            view_att,
            num_rows="dynamic",
            column_config={
                "Entschuldigt": st.column_config.CheckboxColumn("OK?", default=False),
                "Datum": st.column_config.DateColumn("Datum", format="DD.MM.YYYY"),
                "Minuten": st.column_config.NumberColumn(
                    "Netto-Min (ohne Pause)", format="%d"
                ),
                "Schulstunden": st.column_config.NumberColumn(
                    "Stunden (45m)", format="%.1f", disabled=True
                ),
                "Grund": st.column_config.TextColumn("Grund", width="medium"),
                "Halbjahr": st.column_config.TextColumn("Halbjahr", width="small"),
                "Start": st.column_config.TextColumn("Von", width="small"),
                "Ende": st.column_config.TextColumn("Bis", width="small"),
            },
            width="stretch",
            hide_index=True,
        )

        if not edited_att.equals(view_att):
            save_df = edited_att.drop(columns=["Schulstunden"])

            if "Grund" in save_df.columns:
                save_df["Grund"] = save_df["Grund"].fillna("").astype(str)

            save_data(save_df, FILE_ATTENDANCE)
            st.toast("Aktualisiert!", icon="💾")
            force_rerun()

        total_min = df_attendance["Minuten"].sum()
        total_hours = total_min / 45
        open_ex = len(df_attendance[~df_attendance["Entschuldigt"]])

        c_stat1, c_stat2 = st.columns(2)
        c_stat1.metric(
            "Fehlzeiten Gesamt",
            f"{total_hours:.1f} Schulstunden",
            help=f"Entspricht {total_min} Netto-Minuten",
        )
        c_stat2.metric(
            "Offene Entschuldigungen",
            open_ex,
            delta_color="inverse" if open_ex > 0 else "normal",
        )
    else:
        st.info("Keine Fehlzeiten.")

with tab3:
    st.subheader("Zeugnis-Rechner")
    st.warning(
        "⚠️ Hinweis: Die errechneten Noten sind eine rein arithmetische Orientierung. Die pädagogische Endnote auf dem Zeugnis kann (laut LBK) davon abweichen (z.B. durch Gesamtentwicklung)."
    )
    view_hj = st.selectbox("Zeitraum wählen", all_hjs, index=def_hj_idx)

    if view_hj:
        stats_df = calc_stats(df_grades, subjects_config, view_hj)

        if not stats_df.empty:
            stats_df = stats_df.sort_values(by=["Art", "Fach"], ascending=[True, True])

            avg = stats_df["Wert"].mean()
            st.metric(f"Schnitt ({view_hj})", f"{avg:.2f}")
            st.dataframe(
                stats_df,
                column_config={
                    "Wert": None,
                    "Note": st.column_config.TextColumn("Note", help="Endnote"),
                    "Fach": st.column_config.TextColumn("Fach", width="medium"),
                    "Art": st.column_config.TextColumn("Art", width="small"),
                },
                width="content",
                hide_index=True,
            )
        else:
            st.info(f"Keine Daten für {view_hj}.")

with tab4:
    st.header("Fächer verwalten")
    col_add, col_edit = st.columns(2)

    with col_add:
        st.subheader("Fach hinzufügen")
        with st.form("add_sub"):
            new_s = st.text_input("Kürzel (z.B. REL)")
            is_written = st.checkbox(
                "Ist schriftliches Fach? (Hat Klausuren)", value=True
            )

            if st.form_submit_button("Hinzufügen"):
                if new_s and new_s not in subjects_config:
                    start_typ = "Klausur" if is_written else "Sonstige"

                    dummy = {
                        "Datum": datetime.now(),
                        "Halbjahr": "System",
                        "Fach": new_s,
                        "Typ": start_typ,
                        "Eingabe": "0",
                        "Note": 0.0,
                        "Kommentar": "Start",
                    }
                    d_new = pd.DataFrame([dummy])
                    d_new["Datum"] = pd.to_datetime(d_new["Datum"])
                    df_grades = pd.concat([df_grades, d_new], ignore_index=True)
                    save_data(df_grades, FILE_GRADES)
                    st.session_state.new_subject_trigger = f"Fach {new_s} erstellt."
                    force_rerun()
                elif new_s in subjects_config:
                    st.warning("Fach existiert schon.")

    with col_edit:
        st.subheader("Bearbeiten / Löschen")
        edit_sub = st.selectbox("Fach wählen", sorted(list(subjects_config.keys())))

        c_ren, c_del = st.columns(2)
        with c_ren:
            rename_val = st.text_input("Neuer Name", placeholder=edit_sub)
            if st.button("Umbennen"):
                if rename_val and rename_val != edit_sub:
                    df_grades.loc[df_grades["Fach"] == edit_sub, "Fach"] = rename_val
                    save_data(df_grades, FILE_GRADES)
                    st.success(f"Umbennant in {rename_val}")
                    force_rerun()

        with c_del:
            st.write("")
            st.write("")

            st.warning(f"⚠️ Achtung: Löscht ALLE Noten von {edit_sub}!")
            st.info(
                "💡 Tipp: Wenn du ein Fach nur in diesem Halbjahr nicht hast, musst du es NICHT löschen. Einfach keine Note eintragen, dann erscheint es auch nicht im Zeugnis."
            )

            confirm_delete = st.checkbox(
                f"Ja, ich will {edit_sub} wirklich löschen", value=False
            )

            st.markdown(
                """
                <style>
                div[data-testid="stVerticalBlock"] button[kind="primary"] {
                    background-color: #FF4B4B !important;
                    color: white !important;
                    border: none !important;
                }
                div[data-testid="stVerticalBlock"] button[kind="primary"]:hover {
                    background-color: #D32F2F !important;
                }
                div[data-testid="stVerticalBlock"] button[kind="primary"]:disabled {
                    background-color: #555555 !important;
                    color: #888888 !important;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            if st.button(
                "Fach & Historie unwiderruflich löschen",
                type="primary",
                disabled=not confirm_delete,
            ):
                df_grades = df_grades[df_grades["Fach"] != edit_sub]
                save_data(df_grades, FILE_GRADES)
                st.success(f"{edit_sub} gelöscht.")
                force_rerun()

    if st.session_state.new_subject_trigger:
        st.toast(st.session_state.new_subject_trigger, icon="✅")
        st.session_state.new_subject_trigger = None
