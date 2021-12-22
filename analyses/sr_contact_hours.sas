%let dsn = census;

libname &dsn. odbc dsn=&dsn. schema=dbo;

proc sql;
	create table contact as
	select distinct 
		subject_catalog_nbr
  	FROM &dsn..class_vw 
  	where snapshot = 'census' 
  		and strm = '2217' 
  		and total_enrl_hc > 0 
  		and variable_credit_flag = 'N' 
  		and grading_basis = 'GRD'
  	group by subject_catalog_nbr
  	having max(term_contact_hrs) ^= 0 
  	order by subject_catalog_nbr
;quit;

proc sql;
	create table no_contact as
	select distinct 
		subject_catalog_nbr
  	FROM &dsn..class_vw 
  	where snapshot = 'census' 
  		and strm = '2217' 
  		and total_enrl_hc > 0 
  		and variable_credit_flag = 'N' 
  		and grading_basis = 'GRD'
  	group by subject_catalog_nbr
  	having max(term_contact_hrs) = 0 
  	order by subject_catalog_nbr
;qui