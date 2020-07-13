* ------------------------------------------------------------------------------- ;
*                                                                                 ;
*                             STUDENT RISK (1 OF 2)                               ;
*                                                                                 ;
* ------------------------------------------------------------------------------- ;

%let dsn = cendev;
%let adm = adm;
%let lag_year = 1;
%let start_cohort = 2015;
%let end_cohort = 2019;

libname &dsn. odbc dsn=&dsn. schema=dbo;
libname &adm. odbc dsn=&adm. schema=dbo;
libname acs "Z:\Nathan\Models\student_risk\Supplemental Files";

proc import out=act_to_sat_engl_read
	datafile="Z:\Nathan\Models\student_risk\Supplemental Files\act_to_sat_engl_read.xlsx"
	dbms=XLSX REPLACE;
	getnames=YES;
run;

proc import out=act_to_sat_math
	datafile="Z:\Nathan\Models\student_risk\Supplemental Files\act_to_sat_math.xlsx"
	dbms=XLSX REPLACE;
	getnames=YES;
run;

%macro loop;
	
	%do cohort_year=&start_cohort. %to &end_cohort.;
	
	proc sql;
		create table cohort_&cohort_year. as
		select distinct a.*,
			substr(a.last_sch_postal,1,5) as targetid,
			case when a.sex = 'M' then 1 
				else 0
			end as male,
			case when a.age < 18.25 then 'Q1'
				when 18.25 <= a.age < 18.5 then 'Q2'
				when 18.5 <= a.age < 18.75 then 'Q3'
				when 18.75 <= a.age then 'Q4'
				else 'missing'
			end as age_group,
			case when a.father_attended_wsu_flag = 'Y' then 1 
				else 0
			end as father_wsu_flag,
			case when a.mother_attended_wsu_flag = 'Y' then 1 
				else 0
			end as mother_wsu_flag,
			case when a.ipeds_ethnic_group in ('2', '3', '5', '7', 'Z') then 1 
				else 0
			end as underrep_minority,
			case when a.WA_residency = 'RES' then 1
				else 0
			end as resident,
			case when a.adm_parent1_highest_educ_lvl in ('B','C','D','E','F') then '< bach'
				when a.adm_parent1_highest_educ_lvl = 'G' then 'bach'
				when a.adm_parent1_highest_educ_lvl in ('H','I','J','K','L') then '> bach'
					else 'missing'
			end as parent1_highest_educ_lvl,
			case when a.adm_parent2_highest_educ_lvl in ('B','C','D','E','F') then '< bach'
				when a.adm_parent2_highest_educ_lvl = 'G' then 'bach'
				when a.adm_parent2_highest_educ_lvl in ('H','I','J','K','L') then '> bach'
					else 'missing'
			end as parent2_highest_educ_lvl,
			b.distance,
			c.median_inc,
			c.gini_indx,
			d.pvrt_total/d.pvrt_base as pvrt_rate,
			e.educ_rate,
			f.pop/(g.area*3.861E-7) as pop_dens,
			h.median_value,
			i.race_blk/i.race_tot as pct_blk,
			i.race_ai/i.race_tot as pct_ai,
			i.race_asn/i.race_tot as pct_asn,
			i.race_hawi/i.race_tot as pct_hawi,
			i.race_oth/i.race_tot as pct_oth,
			i.race_two/i.race_tot as pct_two,
			(i.race_blk + i.race_ai + i.race_asn + i.race_hawi + i.race_oth + i.race_two)/i.race_tot as pct_non,
			j.ethnic_hisp/j.ethnic_tot as pct_hisp,
			case when k.locale = '11' then 1 else 0 end as city_large,
			case when k.locale = '12' then 1 else 0 end as city_mid,
			case when k.locale = '13' then 1 else 0 end as city_small,
			case when k.locale = '21' then 1 else 0 end as suburb_large,
			case when k.locale = '22' then 1 else 0 end as suburb_mid,
			case when k.locale = '23' then 1 else 0 end as suburb_small,
			case when k.locale = '31' then 1 else 0 end as town_fringe,
			case when k.locale = '32' then 1 else 0 end as town_distant,
			case when k.locale = '33' then 1 else 0 end as town_remote,
			case when k.locale = '41' then 1 else 0 end as rural_fringe,
			case when k.locale = '42' then 1 else 0 end as rural_distant,
			case when k.locale = '43' then 1 else 0 end as rural_remote
		from &dsn..new_student_enrolled_vw as a
		left join acs.distance as b
			on substr(a.last_sch_postal,1,5) = b.targetid
		left join acs.acs_income as c
			on substr(a.last_sch_postal,1,5) = c.geoid
		left join acs.acs_poverty as d
			on substr(a.last_sch_postal,1,5) = d.geoid
		left join acs.acs_education as e
			on substr(a.last_sch_postal,1,5) = e.geoid
		left join acs.acs_demo as f
			on substr(a.last_sch_postal,1,5) = f.geoid
		left join acs.acs_area as g
			on substr(a.last_sch_postal,1,5) = put(g.geoid, 5.)
		left join acs.acs_housing as h
			on substr(a.last_sch_postal,1,5) = h.geoid
		left join acs.acs_race as i
			on substr(a.last_sch_postal,1,5) = i.geoid
		left join acs.acs_ethnicity as j
			on substr(a.last_sch_postal,1,5) = j.geoid
		left join acs.edge_locale14_zcta_table as k
			on substr(a.last_sch_postal,1,5) = k.zcta5ce10
		where a.full_acad_year = "&cohort_year"
			and substr(a.strm, 4 , 1) = '7'
			and a.adj_admit_campus = 'PULLM'
			and a.acad_career = 'UGRD'
			and a.adj_admit_type_cat = 'FRSH'
			and a.ipeds_full_part_time = 'F'
			and a.ipeds_ind = 1
			and a.term_credit_hours > 0
		order by a.emplid
	;quit;
	
	proc sql;
		create table new_student_&cohort_year. as
		select distinct
			emplid,
			pell_recipient_ind,
			eot_term_gpa,
			eot_term_gpa_hours
		from &dsn..new_student_profile_ugrd
		where substr(strm, 4 , 1) = '7'
			and adj_admit_campus = 'PULLM'
			and adj_admit_type = 'FRS'
			and ipeds_full_part_time = 'F'
	;quit;
	
	proc sql;
		create table enrolled_&cohort_year. as
		select distinct 
			emplid, 
			term_code as cont_term,
			enrl_ind
		from &dsn..student_enrolled_vw
		where snapshot = 'census'
			and full_acad_year = put(%eval(&cohort_year. + &lag_year.), 4.)
			and substr(strm, 4, 1) = '7'
			and acad_career = 'UGRD'
			and new_continue_status = 'CTU'
			and term_credit_hours > 0
		order by emplid
	;quit;
	
	proc sql;
		create table plan_&cohort_year. as 
		select distinct 
			emplid,
			acad_plan,
			acad_plan_descr,
			plan_owner_org,
			plan_owner_org_descr,
			plan_owner_group_descrshort,
			case when plan_owner_group_descrshort = 'Business' then 1 else 0 end as business,
			case when plan_owner_group_descrshort = 'CAHNREXT' 
				and plan_owner_org = '03_1240' then 1 else 0 end as cahnrs_anml,
			case when plan_owner_group_descrshort = 'CAHNREXT' 
				and plan_owner_org = '03_1990' then 1 else 0 end as cahnrs_envr,
			case when plan_owner_group_descrshort = 'CAHNREXT' 
				and plan_owner_org = '03_1150' then 1 else 0 end as cahnrs_econ,	
			case when plan_owner_group_descrshort = 'CAHNREXT'
				and plan_owner_org not in ('03_1240','03_1990','03_1150') then 1 else 0 end as cahnrext,
			case when plan_owner_group_descrshort = 'CAS'
				and plan_owner_org = '31_1540' then 1 else 0 end as cas_chem,
			case when plan_owner_group_descrshort = 'CAS'
				and plan_owner_org = '31_1710' then 1 else 0 end as cas_crim,
			case when plan_owner_group_descrshort = 'CAS'
				and plan_owner_org = '31_2530' then 1 else 0 end as cas_math,
			case when plan_owner_group_descrshort = 'CAS'
				and plan_owner_org = '31_2900' then 1 else 0 end as cas_psyc,
			case when plan_owner_group_descrshort = 'CAS'
				and plan_owner_org = '31_8434' then 1 else 0 end as cas_biol,
			case when plan_owner_group_descrshort = 'CAS'
				and plan_owner_org = '31_1830' then 1 else 0 end as cas_engl,
			case when plan_owner_group_descrshort = 'CAS'
				and plan_owner_org = '31_2790' then 1 else 0 end as cas_phys,	
			case when plan_owner_group_descrshort = 'CAS'
				and plan_owner_org not in ('31_1540','31_1710','31_2530','31_2900','31_8434','31_1830','31_2790') then 1 else 0 end as cas,
			case when plan_owner_group_descrshort = 'Comm' then 1 else 0 end as comm,
			case when plan_owner_group_descrshort = 'Education' then 1 else 0 end as education,
			case when plan_owner_group_descrshort in ('Med Sci','Medicine') then 1 else 0 end as medicine,
			case when plan_owner_group_descrshort = 'Nursing' then 1 else 0 end as nursing,
			case when plan_owner_group_descrshort = 'Pharmacy' then 1 else 0 end as pharmacy,
			case when plan_owner_group_descrshort = 'Provost' then 1 else 0 end as provost,
			case when plan_owner_group_descrshort = 'VCEA' 
				and plan_owner_org = '05_1520' then 1 else 0 end as vcea_bioe,
			case when plan_owner_group_descrshort = 'VCEA' 
				and plan_owner_org = '05_1590' then 1 else 0 end as vcea_cive,
			case when plan_owner_group_descrshort = 'VCEA' 
				and plan_owner_org = '05_1260' then 1 else 0 end as vcea_desn,
			case when plan_owner_group_descrshort = 'VCEA' 
				and plan_owner_org = '05_1770' then 1 else 0 end as vcea_eecs,
			case when plan_owner_group_descrshort = 'VCEA' 
				and plan_owner_org = '05_2540' then 1 else 0 end as vcea_mech,
			case when plan_owner_group_descrshort = 'VCEA' 
				and plan_owner_org not in ('05_1520','05_1590','05_1260','05_1770','05_2540') then 1 else 0 end as vcea,				
			case when plan_owner_group_descrshort = 'Vet Med' then 1 else 0 end as vet_med,
			case when plan_owner_group_descrshort not in ('Business','CAHNREXT','CAS','Comm',
														'Education','Med Sci','Medicine','Nursing',
														'Pharmacy','Provost','VCEA','Vet Med') then 1 else 0
			end as groupless,
			case when plan_owner_percent_owned = 50 and plan_owner_org in ('05_1770','03_1990','12_8595') then 1 else 0
			end as split_plan,
			lsamp_stem_flag,
			anywhere_stem_flag
		from &dsn..student_acad_prog_plan_vw
		where snapshot = 'census'
			and full_acad_year = "&cohort_year." /* Note: Was aid_year previously? Why? Check! */
			and substr(strm, 4, 1) = '7'
			and adj_admit_campus = 'PULLM'
			and acad_career = 'UGRD'
			and adj_admit_type_cat = 'FRSH'
			and primary_plan_flag = 'Y'
			and calculated split_plan = 0
	;quit;
	
	proc sql;
		create table need_&cohort_year. as
		select distinct
			a.emplid,
			b.snapshot as need_snap,
			a.aid_year,
			a.fed_efc,
			a.fed_need
		from &dsn..fa_award_period as a
		inner join (select distinct emplid, aid_year, min(snapshot) as snapshot from &dsn..fa_award_period) as b
			on a.emplid = b.emplid
				and a.aid_year = b.aid_year
				and a.snapshot = b.snapshot
		where a.aid_year = "&cohort_year."	
			and a.award_period in ('A','B')
			and a.efc_status = 'O'
	;quit;
	
	proc sql;
		create table aid_&cohort_year. as
		select distinct
			a.emplid,
			b.snapshot as aid_snap,
			a.aid_year,
			sum(a.disbursed_amt) as total_disb,
			sum(a.offer_amt) as total_offer,
			sum(a.accept_amt) as total_accept
		from &dsn..fa_award_aid_year_vw as a
		inner join (select distinct emplid, aid_year, min(snapshot) as snapshot from &dsn..fa_award_aid_year_vw) as b
			on a.emplid = b.emplid
				and a.aid_year = b.aid_year
				and a.snapshot = b.snapshot
		where a.aid_year = "&cohort_year."
			and a.award_period in ('A','B')
			and a.award_status = 'A'
		group by a.emplid;
	;quit;
	
	proc sql;
		create table exams_&cohort_year. as 
		select distinct
			a.emplid,
			a.best,
			a.bestr,
			a.qvalue,
			a.act_engl,
			a.act_read,
			a.act_math,
			largest(1, a.sat_erws, xw_one.sat_erws, xw_three.sat_erws) as sat_erws,
			largest(1, a.sat_mss, xw_two.sat_mss, xw_four.sat_mss) as sat_mss,
			largest(1, (a.sat_erws + a.sat_mss), (xw_one.sat_erws + xw_two.sat_mss), (xw_three.sat_erws + xw_four.sat_mss)) as sat_comp
		from &dsn..new_freshmen_test_score_vw as a
		left join &dsn..xw_sat_i_to_sat_erws as xw_one
			on (a.sat_i_verb + a.sat_i_wr) = xw_one.sat_i_verb_plus_wr
		left join &dsn..xw_sat_i_to_sat_mss as xw_two
 			on a.sat_i_math = xw_two.sat_i_math
 		left join act_to_sat_engl_read as xw_three
 			on (a.act_engl + a.act_read) = xw_three.act_engl_read
		left join act_to_sat_math as xw_four
 			on a.act_math = xw_four.act_math
		where snapshot = 'census'
	;quit;

	proc sql;
		create table degrees_&cohort_year. as
		select distinct
			emplid,
			case when degree = 'AD_AS-T' then 'AD_AST' else degree end as degree,
			1 as ind
		from &dsn..student_ext_degree
		where floor(degree_term_code / 10) <= &cohort_year.
			and degree in ('AD_AS-T','AD_DTA')
		order by emplid
	;quit;
	
	proc transpose data=degrees_&cohort_year. let out=degrees_&cohort_year. (drop=_name_);
		by emplid;
		id degree;
	run;
	
	proc sql;
		create table preparatory_&cohort_year. as
		select distinct
			emplid,
			ext_subject_area,
			1 as ind
		from &dsn..student_ext_acad_subj
		where snapshot = 'census'
			and ext_subject_area in ('CHS','RS', 'AP','IB','AICE')
		order by emplid
	;quit;
	
	proc transpose data=preparatory_&cohort_year. let out=preparatory_&cohort_year. (drop=_name_);
		by emplid;
		id ext_subject_area;
	run;
	
	proc sql;
		create table visitation_&cohort_year. as
		select distinct a.emplid,
			b.snap_date,
			a.attendee_afr_am_scholars_visit,
			a.attendee_alive,
			a.attendee_campus_visit,
			a.attendee_cashe,
			a.attendee_destination,
			a.attendee_experience,
			a.attendee_fcd_pullman,
			a.attendee_fced,
			a.attendee_fcoc,
			a.attendee_fcod,
			a.attendee_group_visit,
			a.attendee_honors_visit,
			a.attendee_imagine_tomorrow,
			a.attendee_imagine_u,
			a.attendee_la_bienvenida,
			a.attendee_lvp_camp,
			a.attendee_oos_destination,
			a.attendee_oos_experience,
			a.attendee_preview,
			a.attendee_preview_jrs,
			a.attendee_shaping,
			a.attendee_top_scholars,
			a.attendee_transfer_day,
			a.attendee_vibes,
			a.attendee_welcome_center,
			a.attendee_any_visitation_ind,
			a.attendee_total_visits
		from &adm..UGRD_visitation_attendee as a
		inner join (select distinct emplid, max(snap_date) as snap_date 
					from &adm..UGRD_visitation_attendee 
					where strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
					group by emplid) as b
			on a.emplid = b.emplid
				and a.snap_date = b.snap_date
		where strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
	;quit;
	
	proc sql;
		create table visitation_detail_&cohort_year. as
		select distinct a.emplid,
			a.snap_date,
			a.go2,
			a.ocv_dt,
			a.ocv_fcd,
			a.ocv_fprv,
			a.ocv_gdt,
			a.ocv_jprv,
			a.ri_col,
			a.ri_fair,
			a.ri_hsv,
			a.ri_nac,
			a.ri_wac,
			a.ri_other,
			a.tap,
			a.tst,
			a.vi_chegg,
			a.vi_crn,
			a.vi_cxc,
			a.vi_mco,
			a.np_group,
			a.out_group,
			a.ref_group,
			a.ocv_da,
			a.ocv_ea,
			a.ocv_fced,
			a.ocv_fcoc,
			a.ocv_fcod,
			a.ocv_oosd,
			a.ocv_oose,
			a.ocv_ve
		from &adm..UGRD_visitation as a
		inner join (select distinct emplid, max(snap_date) as snap_date 
					from &adm..UGRD_visitation 
					where strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
					group by emplid) as b
			on a.emplid = b.emplid
				and a.snap_date = b.snap_date
		where strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
	;quit;
			
	proc sql;
		create table athlete_&cohort_year. as
		select distinct 
			emplid,
			case when (mbaseball = 'Y' 
				or mbasketball = 'Y'
				or mfootball = 'Y'
				or mgolf = 'Y'
				or mitrack = 'Y'
				or motrack = 'Y'
				or mxcountry = 'Y'
				or wbasketball = 'Y'
				or wgolf = 'Y'
				or witrack = 'Y'
				or wotrack = 'Y'
				or wsoccer = 'Y'
				or wswimming = 'Y'
				or wtennis = 'Y'
				or wvolleyball = 'Y'
				or wvrowing = 'Y'
				or wxcountry = 'Y') then 1 else 0
			end as athlete
		from &dsn..student_athlete_vw
		where snapshot = 'census'
			and strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
			and ugrd_adj_admit_type = 'FRS'
	;quit;
	
	proc sql;
		create table remedial_&cohort_year. as
		select distinct
			emplid,
			case when grading_basis_enrl in ('REM','RMS','RMP') 	then 1
																	else 0
																	end as remedial
		from &dsn..class_registration_vw
		where snapshot = 'census'
			and aid_year = "&cohort_year."
			and grading_basis_enrl in ('REM','RMS','RMP')
		order by emplid
	;quit;
	
	proc sql;
		create table date_&cohort_year. as
		select distinct
			min(emplid) as emplid,
			min(week_from_term_begin_dt) as min_week_from_term_begin_dt,
			max(week_from_term_begin_dt) as max_week_from_term_begin_dt,
			count(week_from_term_begin_dt) as count_week_from_term_begin_dt
		from &adm..UGRD_shortened_vw
		where strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
			and ugrd_applicant_counting_ind = 1
		group by emplid
		order by emplid;
	;quit;

	proc sql;
		create table class_registration_&cohort_year. as
		select distinct
			emplid,
			subject_catalog_nbr
		from &dsn..class_registration_vw
		where snapshot = 'census'
			and full_acad_year = "&cohort_year."
	;quit;
	
	proc sql;
		create table class_difficulty_&cohort_year. as
		select distinct
			a.subject_catalog_nbr,
			coalesce(sum(b.total_grade_A), sum(c.total_grade_A)) as total_grade_A,
			(calculated total_grade_A * 4.0) as total_grade_A_GPA,
			coalesce(sum(b.total_grade_A_minus), sum(c.total_grade_A_minus)) as total_grade_A_minus,
			(calculated total_grade_A_minus * 3.7) as total_grade_A_minus_GPA,
			coalesce(sum(b.total_grade_B_plus), sum(c.total_grade_B_plus)) as total_grade_B_plus,
			(calculated total_grade_B_plus * 3.3) as total_grade_B_plus_GPA,
			coalesce(sum(b.total_grade_B), sum(c.total_grade_B)) as total_grade_B,
			(calculated total_grade_B * 3.0) as total_grade_B_GPA,
			coalesce(sum(b.total_grade_B_minus), sum(c.total_grade_B_minus)) as total_grade_B_minus,
			(calculated total_grade_B_minus * 2.7) as total_grade_B_minus_GPA,
			coalesce(sum(b.total_grade_C_plus), sum(c.total_grade_C_plus)) as total_grade_C_plus,
			(calculated total_grade_C_plus * 2.3) as total_grade_C_plus_GPA,
			coalesce(sum(b.total_grade_C), sum(c.total_grade_C)) as total_grade_C,
			(calculated total_grade_C * 2.0) as total_grade_C_GPA,
			coalesce(sum(b.total_grade_C_minus), sum(c.total_grade_C_minus)) as total_grade_C_minus,
			(calculated total_grade_C_minus * 1.7) as total_grade_C_minus_GPA,
			coalesce(sum(b.total_grade_D_plus), sum(c.total_grade_D_plus)) as total_grade_D_plus,
			(calculated total_grade_D_plus * 1.3) as total_grade_D_plus_GPA,
			coalesce(sum(b.total_grade_D), sum(c.total_grade_D)) as total_grade_D,
			(calculated total_grade_D * 1.0) as total_grade_D_GPA,
			coalesce(sum(b.total_grade_F), sum(c.total_grade_F)) as total_grade_F,
			coalesce(sum(b.total_withdrawn), sum(c.total_withdrawn)) as total_withdrawn,
			(calculated total_grade_A + calculated total_grade_A_minus 
				+ calculated total_grade_B_plus + calculated total_grade_B + calculated total_grade_B_minus
				+ calculated total_grade_C_plus + calculated total_grade_C + calculated total_grade_C_minus
				+ calculated total_grade_D_plus + calculated total_grade_D + calculated total_grade_F) as total_grades,
			(calculated total_grade_A_GPA + calculated total_grade_A_minus_GPA 
				+ calculated total_grade_B_plus_GPA + calculated total_grade_B_GPA + calculated total_grade_B_minus_GPA
				+ calculated total_grade_C_plus_GPA + calculated total_grade_C_GPA + calculated total_grade_C_minus_GPA
				+ calculated total_grade_D_plus_GPA + calculated total_grade_D_GPA) as total_grades_GPA,
			(calculated total_grades_GPA / calculated total_grades) as class_average,
			(calculated total_withdrawn / calculated total_grades) as pct_withdrawn,
			(calculated total_grade_C_minus + calculated total_grade_D_plus + calculated total_grade_D 
				+ calculated total_grade_F + calculated total_withdrawn) as CDFW,
			(calculated CDFW / calculated total_grades) as pct_CDFW,
			(calculated total_grade_C_minus + calculated total_grade_D_plus + calculated total_grade_D 
				+ calculated total_grade_F) as CDF,
			(calculated CDF / calculated total_grades) as pct_CDF,
			(calculated total_grade_D_plus + calculated total_grade_D + calculated total_grade_F 
				+ calculated total_withdrawn) as DFW,
			(calculated DFW / calculated total_grades) as pct_DFW,
			(calculated total_grade_D_plus + calculated total_grade_D + calculated total_grade_F) as DF,
			(calculated DF / calculated total_grades) as pct_DF
		from &dsn..class_vw as a
		left join &dsn..class_vw as b
			on a.subject_catalog_nbr = b.subject_catalog_nbr
				and b.snapshot = 'eot'
				and b.full_acad_year = put(%eval(&cohort_year. - &lag_year.), 4.)
				and b.ssr_component = 'LEC'
		left join &dsn..class_vw as c
			on a.subject_catalog_nbr = c.subject_catalog_nbr
				and c.snapshot = 'eot'
				and c.full_acad_year = put(%eval(&cohort_year. - &lag_year.), 4.)
				and c.ssr_component = 'LAB'
		where a.snapshot = 'eot'
			and a.full_acad_year = put(%eval(&cohort_year. - &lag_year.), 4.)
			and a.ssr_component in ('LEC','LAB')
		group by a.subject_catalog_nbr
		order by a.subject_catalog_nbr
	;quit;
	
	proc sql;
		create table coursework_difficulty_&cohort_year. as
		select
			a.emplid,
			count(a.subject_catalog_nbr) as class_count,
			avg(b.class_average) as avg_difficulty,
			avg(b.pct_withdrawn) as avg_pct_withdrawn,
			avg(b.pct_CDFW) as avg_pct_CDFW,
			avg(b.pct_CDF) as avg_pct_CDF,
			avg(b.pct_DFW) as avg_pct_DFW,
			avg(b.pct_DF) as avg_pct_DF
		from class_registration_&cohort_year. as a
		left join class_difficulty_&cohort_year. as b
			on a.subject_catalog_nbr = b.subject_catalog_nbr
		group by a.emplid
	;quit;
	
	proc sql;
		create table term_contact_hrs_&cohort_year. as
		select distinct
			a.emplid,
			sum(b.lec_contact_hrs) as lec_contact_hrs,
			sum(c.lab_contact_hrs) as lab_contact_hrs
		from class_registration_&cohort_year. as a
		left join (select distinct
						subject_catalog_nbr,
						max(term_contact_hrs) as lec_contact_hrs
					from &dsn..class_vw
					where snapshot = 'census'
						and full_acad_year = put(%eval(&cohort_year.), 4.)
						and ssr_component = 'LEC'
					group by subject_catalog_nbr) as b
			on a.subject_catalog_nbr = b.subject_catalog_nbr
		left join (select distinct
						subject_catalog_nbr,
						max(term_contact_hrs) as lab_contact_hrs
					from &dsn..class_vw
					where snapshot = 'census'
						and full_acad_year = put(%eval(&cohort_year.), 4.)
						and ssr_component = 'LAB'
					group by subject_catalog_nbr ) as c
			on a.subject_catalog_nbr = c.subject_catalog_nbr
		group by a.emplid
	;quit;
	
	proc sql;
		create table exams_detail_&cohort_year. as
		select distinct
			emplid,
			max(sat_sup_rwc) as sat_sup_rwc,
			max(sat_sup_ce) as sat_sup_ce,
			max(sat_sup_ha) as sat_sup_ha,
			max(sat_sup_psda) as sat_sup_psda,
			max(sat_sup_ei) as sat_sup_ei,
			max(sat_sup_pam) as sat_sup_pam,
			max(sat_sup_sec) as sat_sup_sec
		from &dsn..student_test_comp_sat_w
		where snapshot = 'census'
		group by emplid
	;quit;
	
	proc sql;
		create table housing_&cohort_year. as
		select distinct
			emplid,
			camp_addr_indicator,
			housing_reshall_indicator,
			housing_ssa_indicator,
			housing_family_indicator,
			afl_reshall_indicator,
			afl_ssa_indicator,
			afl_family_indicator,
			afl_greek_indicator,
			afl_greek_life_indicator
		from &dsn..new_student_enrolled_housing_vw
		where snapshot = 'census'
			and strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
			and adj_admit_campus = 'PULLM'
			and acad_career = 'UGRD'
			and adj_admit_type_cat = 'FRSH'
	;quit;
	
	proc sql;
		create table housing_detail_&cohort_year. as
		select distinct
			emplid,
			'#' || put(building_id, z2.) as building_id
		from &dsn..student_housing
		where snapshot = 'census'
			and strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
	;quit;
	
	proc sql;
		create table dataset_&cohort_year. as
		select 
			a.*,
			b.pell_recipient_ind,
			b.eot_term_gpa,
			b.eot_term_gpa_hours,
			c.cont_term,
			c.enrl_ind,
			d.acad_plan,
			d.acad_plan_descr,
			d.plan_owner_org,
			d.plan_owner_org_descr,
			d.plan_owner_group_descrshort,
			d.business,
			d.cahnrs_anml,
			d.cahnrs_envr,
			d.cahnrs_econ,
			d.cahnrext,
			d.cas_chem,
			d.cas_crim,
			d.cas_math,
			d.cas_psyc,
			d.cas_biol,
			d.cas_engl,
			d.cas_phys,
			d.cas,
			d.comm,
			d.education,
			d.medicine,
			d.nursing,
			d.pharmacy,
			d.provost,
			d.vcea_bioe,
			d.vcea_cive,
			d.vcea_desn,
			d.vcea_eecs,
			d.vcea_mech,
			d.vcea,
			d.vet_med,
			d.lsamp_stem_flag,
			d.anywhere_stem_flag,
			e.need_snap,
			e.fed_efc,
			e.fed_need,
			f.aid_snap,
			f.total_disb,
			f.total_offer,
			f.total_accept,
			g.best,
			g.bestr,
			g.qvalue,
			g.act_engl,
			g.act_read,
			g.act_math,
			g.sat_erws,
			g.sat_mss,
			g.sat_comp,
			h.ad_dta,
			h.ad_ast,
			i.ap,
			i.rs,
			i.chs,
			i.ib,
			i.aice,
			largest(1, i.ib, i.aice) as IB_AICE,
			j.attendee_alive,
			j.attendee_campus_visit,
			j.attendee_cashe,
			j.attendee_destination,
			j.attendee_experience,
			j.attendee_fcd_pullman,
			j.attendee_fced,
			j.attendee_fcoc,
			j.attendee_fcod,
			j.attendee_group_visit,
			j.attendee_honors_visit,
			j.attendee_imagine_tomorrow,
			j.attendee_imagine_u,
			j.attendee_la_bienvenida,
			j.attendee_lvp_camp,
			j.attendee_oos_destination,
			j.attendee_oos_experience,
			j.attendee_preview,
			j.attendee_preview_jrs,
			j.attendee_shaping,
			j.attendee_top_scholars,
			j.attendee_transfer_day,
			j.attendee_vibes,
			j.attendee_welcome_center,
			j.attendee_any_visitation_ind,
			j.attendee_total_visits,
			k.athlete,
			l.remedial,
			m.min_week_from_term_begin_dt,
			m.max_week_from_term_begin_dt,
			m.count_week_from_term_begin_dt,
			n.class_count,
			(4.0 - n.avg_difficulty) as avg_difficulty,
			n.avg_pct_withdrawn,
			n.avg_pct_CDFW,
			n.avg_pct_CDF,
			n.avg_pct_DFW,
			n.avg_pct_DF,
			o.lec_contact_hrs,
			o.lab_contact_hrs,
			p.sat_sup_rwc,
			p.sat_sup_ce,
			p.sat_sup_ha,
			p.sat_sup_psda,
			p.sat_sup_ei,
			p.sat_sup_pam,
			p.sat_sup_sec,
			q.camp_addr_indicator,
			q.housing_reshall_indicator,
			q.housing_ssa_indicator,
			q.housing_family_indicator,
			q.afl_reshall_indicator,
			q.afl_ssa_indicator,
			q.afl_family_indicator,
			q.afl_greek_indicator,
			q.afl_greek_life_indicator,
			r.building_id
		from cohort_&cohort_year. as a
		left join new_student_&cohort_year. as b
			on a.emplid = b.emplid
		left join enrolled_&cohort_year. as c
			on a.emplid = c.emplid
 				and a.term_code + 10 = c.cont_term
 		left join plan_&cohort_year. as d
 			on a.emplid = d.emplid
 		left join need_&cohort_year. as e
 			on a.emplid = e.emplid
 				and a.aid_year = e.aid_year
 		left join aid_&cohort_year. as f
 			on a.emplid = f.emplid
 				and a.aid_year = f.aid_year
 		left join exams_&cohort_year. as g
 			on a.emplid = g.emplid
 		left join degrees_&cohort_year. as h
 			on a.emplid = h.emplid
 		left join preparatory_&cohort_year. as i
 			on a.emplid = i.emplid
 		left join visitation_&cohort_year. as j
 			on a.emplid = j.emplid
 		left join athlete_&cohort_year. as k
 			on a.emplid = k.emplid
		left join remedial_&cohort_year. as l
 			on a.emplid = l.emplid
 		left join date_&cohort_year. as m
 			on a.emplid = m.emplid
 		left join coursework_difficulty_&cohort_year. as n
 			on a.emplid = n.emplid
 		left join term_contact_hrs_&cohort_year. as o
 			on a.emplid = o.emplid
 		left join exams_detail_&cohort_year. as p
 			on a.emplid = p.emplid
 		left join housing_&cohort_year. as q
 			on a.emplid = q.emplid
 		 left join housing_detail_&cohort_year. as r
 			on a.emplid = r.emplid
	;quit;
	
	%end;
	
%mend loop;

%loop;

data full_set;
	set dataset_&start_cohort.-dataset_&end_cohort.;
	if enrl_ind = . then enrl_ind = 0;
	if ad_dta = . then ad_dta = 0;
	if ad_ast = . then ad_ast = 0;
	if ap = . then ap = 0;
	if rs = . then rs = 0;
	if chs = . then chs = 0;
	if ib = . then ib = 0;
	if aice = . then aice = 0;
	if ib_aice = . then ib_aice = 0;
	if athlete = . then athlete = 0;
	if fed_efc = . then fed_efc = 0;
	if fed_need = . then fed_need = 0;
	if total_disb = . then total_disb = 0;
	if total_offer = . then total_offer = 0;
	if total_accept = . then total_accept = 0;	
	if remedial = . then remedial = 0;
	if last_sch_proprietorship = '' then last_sch_proprietorship = 'UNKN';
	if ipeds_ethnic_group_descrshort = '' then ipeds_ethnic_group_descrshort = 'NS';
	if avg_difficulty = . then avg_difficulty = 0;
	if lec_contact_hrs = . then lec_contact_hrs = 0;
	if lab_contact_hrs = . then lab_contact_hrs = 0;
	if camp_addr_indicator ^= 'Y' then camp_addr_indicator = 'N';
	if housing_reshall_indicator ^= 'Y' then housing_reshall_indicator = 'N';
	if housing_ssa_indicator ^= 'Y' then housing_ssa_indicator = 'N';
	if housing_family_indicator ^= 'Y' then housing_family_indicator = 'N';
	if afl_reshall_indicator ^= 'Y' then afl_reshall_indicator = 'N';
	if afl_ssa_indicator ^= 'Y' then afl_ssa_indicator = 'N';
	if afl_family_indicator ^= 'Y' then afl_family_indicator = 'N';
	if afl_greek_indicator ^= 'Y' then afl_greek_indicator = 'N';
	if afl_greek_life_indicator ^= 'Y' then afl_greek_life_indicator = 'N';
	unmet_need_disb = fed_need - total_disb;
	unmet_need_acpt = fed_need - total_accept;
	unmet_need_ofr = fed_need - total_offer;
run;

/* Note: There should be no duplicates */
proc sort data=full_set nodupkey dupout=dups;
	by emplid;
run;

/* proc means data=full_set median q1 q3; */
/* 	var age; */
/* run; */

data training_set;
	set dataset_&start_cohort.-dataset_%eval(&end_cohort. - &lag_year.);
	if enrl_ind = . then enrl_ind = 0;
	if ad_dta = . then ad_dta = 0;
	if ad_ast = . then ad_ast = 0;
	if ap = . then ap = 0;
	if rs = . then rs = 0;
	if chs = . then chs = 0;
	if ib = . then ib = 0;
	if aice = . then aice = 0;
	if ib_aice = . then ib_aice = 0;	
	if athlete = . then athlete = 0;
	if fed_efc = . then fed_efc = 0;
	if fed_need = . then fed_need = 0;
	if total_disb = . then total_disb = 0;
	if total_offer = . then total_offer = 0;
	if total_accept = . then total_accept = 0;
	if remedial = . then remedial = 0;
	if last_sch_proprietorship = '' then last_sch_proprietorship = 'UNKN';
	if ipeds_ethnic_group_descrshort = '' then ipeds_ethnic_group_descrshort = 'NS';
	if avg_difficulty = . then avg_difficulty = 0;
	if lec_contact_hrs = . then lec_contact_hrs = 0;
	if lab_contact_hrs = . then lab_contact_hrs = 0;
	if camp_addr_indicator ^= 'Y' then camp_addr_indicator = 'N';
	if housing_reshall_indicator ^= 'Y' then housing_reshall_indicator = 'N';
	if housing_ssa_indicator ^= 'Y' then housing_ssa_indicator = 'N';
	if housing_family_indicator ^= 'Y' then housing_family_indicator = 'N';
	if afl_reshall_indicator ^= 'Y' then afl_reshall_indicator = 'N';
	if afl_ssa_indicator ^= 'Y' then afl_ssa_indicator = 'N';
	if afl_family_indicator ^= 'Y' then afl_family_indicator = 'N';
	if afl_greek_indicator ^= 'Y' then afl_greek_indicator = 'N';
	if afl_greek_life_indicator ^= 'Y' then afl_greek_life_indicator = 'N';
	unmet_need_disb = fed_need - total_disb;
	unmet_need_acpt = fed_need - total_accept;
	unmet_need_ofr = fed_need - total_offer;
run;

data testing_set;
	set dataset_&end_cohort.;
	if enrl_ind = . then enrl_ind = 0;
	if ad_dta = . then ad_dta = 0;
	if ad_ast = . then ad_ast = 0;
	if ap = . then ap = 0;
	if rs = . then rs = 0;
	if chs = . then chs = 0;
	if ib = . then ib = 0;
	if aice = . then aice = 0;
	if ib_aice = . then ib_aice = 0;
	if athlete = . then athlete = 0;
	if fed_efc = . then fed_efc = 0;
	if fed_need = . then fed_need = 0;
	if total_disb = . then total_disb = 0;
	if total_offer = . then total_offer = 0;
	if total_accept = . then total_accept = 0;
	if remedial = . then remedial = 0;
	if last_sch_proprietorship = '' then last_sch_proprietorship = 'UNKN';
	if ipeds_ethnic_group_descrshort = '' then ipeds_ethnic_group_descrshort = 'NS';
	if avg_difficulty = . then avg_difficulty = 0;
	if lec_contact_hrs = . then lec_contact_hrs = 0;
	if lab_contact_hrs = . then lab_contact_hrs = 0;
	if camp_addr_indicator ^= 'Y' then camp_addr_indicator = 'N';
	if housing_reshall_indicator ^= 'Y' then housing_reshall_indicator = 'N';
	if housing_ssa_indicator ^= 'Y' then housing_ssa_indicator = 'N';
	if housing_family_indicator ^= 'Y' then housing_family_indicator = 'N';
	if afl_reshall_indicator ^= 'Y' then afl_reshall_indicator = 'N';
	if afl_ssa_indicator ^= 'Y' then afl_ssa_indicator = 'N';
	if afl_family_indicator ^= 'Y' then afl_family_indicator = 'N';
	if afl_greek_indicator ^= 'Y' then afl_greek_indicator = 'N';
	if afl_greek_life_indicator ^= 'Y' then afl_greek_life_indicator = 'N';
	unmet_need_disb = fed_need - total_disb;
	unmet_need_acpt = fed_need - total_accept;
	unmet_need_ofr = fed_need - total_offer;
run;

filename full "Z:\Nathan\Models\student_risk\full_set.csv" encoding="utf-8";

proc export data=full_set outfile=full dbms=csv replace;
run;

filename training "Z:\Nathan\Models\student_risk\training_set.csv" encoding="utf-8";

proc export data=training_set outfile=training dbms=csv replace;
run;

filename testing "Z:\Nathan\Models\student_risk\testing_set.csv" encoding="utf-8";

proc export data=testing_set outfile=testing dbms=csv replace;
run;
