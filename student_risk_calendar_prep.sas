%let dsn = census;

libname &dsn. odbc dsn=&dsn. schema=dbo;

proc sql;
    create table acad_calendar as
    select distinct
        *
        ,intnx('dtday', term_census_dt, 10, 'same') as adj_term_census_dt format=datetime22.3
    from &dsn..xw_term
    where acad_career = 'UGRD'
    order by term_code
;quit;

proc sql;
    create table adj_acad_calendar as
    select distinct
        *
        ,day(datepart(term_begin_dt)) as begin_day
        ,month(datepart(term_begin_dt)) as begin_month
        ,year(datepart(term_begin_dt)) as begin_year
        ,day(datepart(adj_term_census_dt)) as census_day
        ,month(datepart(adj_term_census_dt)) as census_month
        ,year(datepart(adj_term_census_dt)) as census_year
        ,day(datepart(term_end_dt)) as end_day
        ,month(datepart(term_end_dt)) as end_month
        ,year(datepart(term_end_dt)) as end_year
    from acad_calendar
    order by term_code
;quit;

filename calendar "Z:\Nathan\Models\student_risk\Supplemental Files\acad_calendar.csv" encoding="utf-8";

proc export data=acad_calendar outfile=calendar dbms=csv replace;
run;