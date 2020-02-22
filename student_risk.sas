* ---------------------------------------------------------------------- ;
*                                                                        ;
*                             STUDENT RISK                               ;
*                                                                        ;
* ---------------------------------------------------------------------- ;

%let dsn = cendev;
%let lag_year = 1;
%let start_cohort = 2015;
%let end_cohort = 2019;

libname &dsn. odbc dsn=&dsn. schema=dbo;

proc import out=distance
	datafile="Z:\Nathan\Models\student_risk\Supplemental Files\distance_matrix.csv"
	dbms=CSV REPLACE;
	getnames=YES;
run;

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
			b.distance
		from &dsn..new_student_enrolled_vw as a
		inner join (select distinct targetid, distance from distance) as b
			on substr(a.last_sch_postal,1,5) = b.targetid
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
			case when plan_owner_group_descrshort = 'CAHNREXT' then 1 else 0 end as cahnrext,
			case when plan_owner_group_descrshort = 'CAS' then 1 else 0 end as cas,
			case when plan_owner_group_descrshort = 'Comm' then 1 else 0 end as comm,
			case when plan_owner_group_descrshort = 'Education' then 1 else 0 end as education,
			case when plan_owner_group_descrshort = 'Med Sci' then 1 else 0 end as med_sci,
			case when plan_owner_group_descrshort = 'Medicine' then 1 else 0 end as medicine,
			case when plan_owner_group_descrshort = 'Nursing' then 1 else 0 end as nursing,
			case when plan_owner_group_descrshort = 'Pharmacy' then 1 else 0 end as pharmacy,
			case when plan_owner_group_descrshort = 'Provost' then 1 else 0 end as provost,
			case when plan_owner_group_descrshort = 'VCEA' then 1 else 0 end as vcea,
			case when plan_owner_group_descrshort = 'Vet Med' then 1 else 0 end as vet_med,
			case when plan_owner_group_descrshort not in ('Business','CAHNREXT','CAS','Comm',
														'Education','Med Sci','Medicine','Nursing',
														'Pharmacy','Provost','VCEA','Vet Med') then 1 else 0
			end as groupless,
			lsamp_stem_flag
		from &dsn..student_acad_prog_plan_vw
		where snapshot = 'census'
			and aid_year = "&cohort_year."
			and substr(strm, 4, 1) = '7'
			and adj_admit_campus = 'PULLM'
			and acad_career = 'UGRD'
			and adj_admit_type_cat = 'FRSH'
			and primary_plan_flag = 'Y'
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
		inner join (select distinct aid_year, min(snapshot) as snapshot from &dsn..fa_award_period) as b
			on a.aid_year = b.aid_year
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
		inner join (select distinct aid_year, min(snapshot) as snapshot from &dsn..fa_award_aid_year_vw) as b
			on a.aid_year = b.aid_year
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
			largest(1, a.sat_mss, xw_two.sat_mss, xw_four.sat_mss) as sat_mss
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
			d.cahnrext,
			d.cas,
			d.comm,
			d.education,
			d.med_sci,
			d.medicine,
			d.nursing,
			d.pharmacy,
			d.provost,
			d.vcea,
			d.vet_med,
			d.lsamp_stem_flag,
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
			h.ad_dta,
			h.ad_ast,
			i.ap,
			i.rs,
			i.chs,
			i.ib,
			i.aice
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
	if fed_efc = . then fed_efc = 0;
	if fed_need = . then fed_need = 0;
	if total_disb = . then total_disb = 0;
	if total_offer = . then total_offer = 0;
	if total_accept = . then total_accept = 0;	
	if last_sch_proprietorship = '' then last_sch_proprietorship = 'UNKN';
	if ipeds_ethnic_group_descrshort = '' then ipeds_ethnic_group_descrshort = 'NS';
	unmet_need_disb = fed_need - total_disb;
	unmet_need_acpt = fed_need - total_accept;
	unmet_need_ofr = fed_need - total_offer;
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
	if fed_efc = . then fed_efc = 0;
	if fed_need = . then fed_need = 0;
	if total_disb = . then total_disb = 0;
	if total_offer = . then total_offer = 0;
	if total_accept = . then total_accept = 0;
	if last_sch_proprietorship = '' then last_sch_proprietorship = 'UNKN';
	if ipeds_ethnic_group_descrshort = '' then ipeds_ethnic_group_descrshort = 'NS';
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
	if fed_efc = . then fed_efc = 0;
	if fed_need = . then fed_need = 0;
	if total_disb = . then total_disb = 0;
	if total_offer = . then total_offer = 0;
	if total_accept = . then total_accept = 0;
	if last_sch_proprietorship = '' then last_sch_proprietorship = 'UNKN';
	if ipeds_ethnic_group_descrshort = '' then ipeds_ethnic_group_descrshort = 'NS';
	unmet_need_disb = fed_need - total_disb;
	unmet_need_acpt = fed_need - total_accept;
	unmet_need_ofr = fed_need - total_offer;
run;

filename full 'Z:/Nathan/Models/student_risk/full_set.csv' encoding="utf-8";

proc export data=full_set outfile=full dbms=csv replace;
run;

filename training 'Z:/Nathan/Models/student_risk/training_set.csv' encoding="utf-8";

proc export data=training_set outfile=training dbms=csv replace;
run;

filename testing 'Z:/Nathan/Models/student_risk/testing_set.csv' encoding="utf-8";

proc export data=testing_set outfile=testing dbms=csv replace;
run;
