libname sas "C:\Users\nathan.lindstedt\Desktop\student_risk_distance\";

proc import out=distance_import
	datafile="C:\Users\nathan.lindstedt\Desktop\student_risk_distance\distance_matrix.xlsx"
	dbms=XLSX REPLACE;
	getnames=YES;
run;

proc sort data=distance_import;
	by inputid;
run;

data distance_recode;
	set distance_import;
	campus = '     ';
	if targetid = '99163' then campus = 'PULLM';
	if targetid = '99354' then campus = 'TRICI';
	if targetid = '98686' then campus = 'VANCO';
	if targetid = '99202' then campus = 'SPOKA';
	if targetid = '98201' then campus = 'EVERE';
run;

proc transpose data=distance_recode out=distance_transpose suffix=_distance_km let;
	id campus;
	by inputid;
	var distance;
run;

data sas.distance_km;
	set distance_transpose;
	VANCO_distance_km = VANCO_distance_km / 1000;
	TRICI_distance_km = TRICI_distance_km / 1000;
	PULLM_distance_km = PULLM_distance_km / 1000;
	SPOKA_distance_km = SPOKA_distance_km / 1000;
	EVERE_distance_km = EVERE_distance_km / 1000;
	drop _name_ _label_;
run;
