from flask import Flask, render_template, request, flash, redirect, url_for
import json
from database import PostgresqlDB

USER_NAME = 'postgres'
PASSWORD = 'postgres'
PORT = 5432
DATABASE_NAME = 'bank'
HOST = 'localhost'

db = PostgresqlDB(user_name=USER_NAME,
                  password=PASSWORD,
                  host=HOST,port=PORT,
                  db_name=DATABASE_NAME)
engine = db.engine

app = Flask(__name__)
app.secret_key = "adnanisgreat"

def run_begin():
    q = '''create or replace procedure create_loan(cid int,l_amount numeric,l_type varchar(50),l_duration int,int_rate numeric)
    as $$
    begin
    insert into loan(loan_id,loan_amount,loan_type,loan_duration_months,interest_rate,branch_code)
    values((select max(loan_id) from loan)+1,l_amount,l_type,l_duration,int_rate,
        (select branch_code from branch where branch_city=(select city_name from customer where customer_id=cid)));
    insert into borrower(customer_id,loan_id) 
    values (cid,(select max(loan_id) from loan));
    insert into payment(payment_id,payment_amount,payment_date,loan_id)
    values((select max(payment_id) from payment)+1,0,current_date,(select max(loan_id) from loan));
    end;$$ language plpgsql;

    --trigger to get monthly payment
    create or replace function get_payment()
    returns trigger
    as $$
    declare pay_amount int;
    begin
    pay_amount = ((select loan_amount from loan where loan_id=(select max(loan_id) from loan))*((select interest_rate from loan where loan_id=(select max(loan_id) from loan))/(12*100))*power(1+((select interest_rate from loan where loan_id=(select max(loan_id) from loan))/(12*100)),(select loan_duration_months from loan where loan_id=(select max(loan_id) from loan)))/(power(1+((select interest_rate from loan where loan_id=(select max(loan_id) from loan))/(12*100)),(select loan_duration_months from loan where loan_id=(select max(loan_id) from loan)))-1));
    update loan 
    set monthly_payment=pay_amount where loan_id=(select max(loan_id) from loan);	
    return new;
    end;$$ language plpgsql;

    create or replace trigger get_monthly_payment
    after insert
    on loan
    for each row
    execute procedure get_payment();
        
    create or replace procedure create_another_account(cid int,acc_type varchar(50))
    as $$
    begin
    if(acc_type = any(select account.account_type from customer,depositor,account where customer.customer_id=cid and customer.customer_id=depositor.customer_id and depositor.account_id=account.account_id)) then 
        raise notice 'account type already exisits';
    else 
        insert into account(account_id,account_type,branch_code)
        values (((select max(account_id) from account)+1),acc_type,(select branch_code from branch where branch_city=(select city_name from customer where customer_id=cid)));
        insert into depositor(customer_id,account_id,access_date) 
        values((select customer_id from customer where customer_id=cid),(select max(account_id) from account),current_date);
    end if;
    end;$$ language plpgsql;
    create or replace function give_bal()
    returns trigger
    as $$
    begin
    if((select account_type from account where account_id=new.account_id)= 'Zero Balance Account') then
        update account 
        set balance=0
        where account_id=new.account_id;
        return new;
    else
        update account 
        set balance=5000
        where account_id=new.account_id;
        return new;
    end if;
    end;$$ language plpgsql;

    create or replace trigger give_cal
    after insert
    on account
    for each row
    execute procedure give_bal();

    create or replace procedure Transfer(sid int, rid int, amount numeric)
    as $$
    begin 
    if((select balance from account where account_id=sid ) < amount) then
        raise notice 'insufficient balance in sender account';
    else
        update account 
        set balance=balance-amount where account_id=sid;
        update account 
        set balance=balance+amount where account_id=rid;
        update depositor 
        set access_date=current_date where account_id=sid;
    end if;
    end;$$ language plpgsql;
    create or replace procedure create_new_account(fullname varchar(50),dob date,c_name varchar(50),s_name varchar(50),p_no varchar(12),acc_type varchar(50))
    as $$
    begin
    insert into customer(customer_id,customer_name,birth_date,city_name,state_name,phone_number)
    values((select max(customer_id) from customer)+1,fullname,dob,c_name,s_name,p_no);
    insert into account(account_id,account_type,branch_code)
    values (((select max(account_id) from account)+1),acc_type,(select branch_code from branch where branch_city=c_name));
    insert into depositor(customer_id,account_id,access_date) 
    values ((select max(customer_id) from customer),(select max(account_id) from account),current_date);
    end;$$ language plpgsql;
    create or replace function give_bal()
    returns trigger
    as $$
    begin
    if((select account_type from account where account_id=new.account_id)= 'Zero Balance Account') then
        update account 
        set balance=0
        where account_id=new.account_id;
        return new;
    else
        update account 
        set balance=5000
        where account_id=new.account_id;
        return new;
    end if;
    end;$$ language plpgsql;

    create or replace trigger give_cal
    after insert
    on account
    for each row
    execute procedure give_bal();
    create or replace procedure Withdraw(amount numeric,aid int)
    as $$
    begin
    if((select balance from account where account_id=aid) < amount) then 
        raise notice 'insufficient balance in account';
    else
        update account 
        set balance=balance-amount where account_id=aid;
        update depositor 
        set access_date=current_date where account_id=aid;
    end if;
    end;$$ language plpgsql;
    create or replace procedure Deposit(amount_deposited numeric, aid int)
    as $$
    begin
    update account
    set balance = balance + amount_deposited
    where account_id = aid;
    update depositor
    set access_date = current_date
    where account_id = aid;
    end;$$ language plpgsql;
    create or replace procedure pay_bills(cid int, aid int, lid int)
    as $$
    declare amount int;
    declare bal int;
    declare monthly_amt numeric;
    begin
    select loan.monthly_payment from loan join borrower on borrower.loan_id = loan.loan_id
    join customer on customer.customer_id = borrower.customer_id where customer.customer_id = cid and loan.loan_id=lid into amount;
    select balance from account where account_id = aid into bal;
    if amount>bal then raise exception 'insufficient balance';
    else
    update account
    set balance = balance - amount, last_updated = current_date where account_id = aid;
    update loan
    set loan_amount = loan_amount - amount where loan_id = lid;
    insert into payment_log values(cid,aid,lid);
    end if;
    end;$$ language plpgsql;

    create or replace function update_payment()
    returns trigger as $$
    declare amount numeric;
    declare lid int;
    begin
    lid = new.lid;
    select monthly_payment from loan where loan_id = lid into amount;
    insert into payment (payment_id,payment_amount, payment_date, loan_id)
    values ((select max(payment_id) from payment)+1,amount, current_date, lid);
    update loan
    set monthly_payment = ((select loan_amount from loan where loan_id=lid)*((select interest_rate from loan where loan_id=lid)/(12*100))*power(1+((select interest_rate from loan where loan_id=lid)/(12*100)),(select loan_duration_months from loan where loan_id=lid))/(power(1+((select interest_rate from loan where loan_id=lid)/(12*100)),(select loan_duration_months from loan where loan_id=lid))-1))
    where loan_id = lid;
    return new;
    end;$$ language plpgsql;

    create or replace trigger pay_update
    after insert on payment_log
    for each row
    execute function update_payment();
    '''
    db.execute_ddl_and_dml_commands(q)
def changeRole(user):
	query = '''set role to :user'''
	db.execute_ddl_and_dml_commands(query, values={'user': user})


def checkUser():
	query = '''select current_user'''
	result = db.execute_dql_commands(query)
	for row in result:
		return row
def depositMoney(cid,amount, aid):
	new_query = '''insert into task values (:cid, :task_type, :task_desc, :done)'''
	task_desc_json = {
		"amount" : amount,
        "aid" : aid
	}
	task_text = json.dumps(task_desc_json)
	db.execute_ddl_and_dml_commands(new_query, values={'cid': cid, 'task_type': 'D', 'task_desc': task_text, 'done': 0})


def withdrawMoney(cid,amount, aid):
	new_query = '''insert into task values (:cid, :task_type, :task_desc, :done)'''
	task_desc_json = {
          "amount" : amount,
          "aid" : aid
	}
	task_text = json.dumps(task_desc_json)
	db.execute_ddl_and_dml_commands(new_query, values={'cid': cid, 'task_type': 'W', 'task_desc': task_text, 'done': 0})


def createNewCustomer(fullname, dob, c_name, s_name, p_no, acc_type):
	new_query = '''insert into task values (:cid, :task_type, :task_desc, :done)'''
	task_desc_json = {
            "fullname" : fullname,
            "dob" : dob,
            "c_name" : c_name,
            "s_name" : s_name,
            "p_no" : p_no,
            "acc_type" : acc_type
	}
	task_text = json.dumps(task_desc_json)
	db.execute_ddl_and_dml_commands(new_query, values={'cid': -1, 'task_type': 'N', 'task_desc': task_text, 'done': 0})


def transferAmount(cid, sid, rid, amount):
	new_query = '''insert into task values (:cid, :task_type, :task_desc, :done)'''
	task_desc_json = {
		"sid" : sid,
		"rid" : rid,
		"amount" : amount
	}
	task_text = json.dumps(task_desc_json)
	db.execute_ddl_and_dml_commands(new_query, values={'cid': cid, 'task_type': 'T', 'task_desc': task_text, 'done': 0})


def createNewAccount(cid, acc_type):
	new_query = '''insert into task values (:cid, :task_type, :task_desc, :done)'''
	task_desc_json = {
		"acc_type" : acc_type
	}
	task_text = json.dumps(task_desc_json)
	db.execute_ddl_and_dml_commands(new_query, values={'cid': cid, 'task_type': 'E', 'task_desc': task_text, 'done': 0})


def fetchCustomerUsingId(cid):
    query = "SELECT * FROM customer WHERE customer_id = :cid"
    result = db.execute_dql_commands(query, values={'cid': cid})
    for row in result:
        return row

def fetchCustomer(customer_name):
    query = "SELECT * FROM customer WHERE customer_name = :name"
    result = db.execute_dql_commands(query, values={'name': customer_name})
    for row in result:
        return row

def fetchAccount(accid):
    query = "SELECT * FROM account WHERE account_id = :id"
    result = db.execute_dql_commands(query, values={'id': accid})
    account = result.fetchone()
    return account


def fetchCustomerAccBalance(customer_id):
    query = '''create or replace function Show_balance (cid int)
               returns table(account_id int, account_type varchar(50), balance numeric)
               as $$
               begin
                return query
                select Account.account_id, Account.account_type, Account.balance from Customer, Depositor, Account
                where Customer.customer_id = cid 
                and Customer.customer_id = Depositor.customer_id
                and Depositor.account_id = Account.account_id;
               end; $$ language plpgsql;'''
    query2 = '''select * from Show_balance (:cid);'''
    result = db.execute_dql_commands(query2, values={'cid': customer_id})
    account_info = []
    for row in result:
        account_info.append({"account_type": row.account_type, "balance": row.balance})
    return account_info


def createLoan(cid, l_amount, l_type, l_duration, int_rate):
	new_query = '''insert into task values (:cid, :task_type, :task_desc, :done)'''
	task_desc_json = {
	"l_amount": l_amount,
	"l_type": l_type,
	"l_duration": l_duration,
	"int_rate": int_rate
	}
	task_text = json.dumps(task_desc_json)
	db.execute_ddl_and_dml_commands(new_query, values={'cid': cid, 'task_type': 'L', 'task_desc': task_text, 'done': 0})

def fetchLoanDetails(cid):
	query = '''select loan.loan_id, loan_type,loan_amount,start_date,monthly_payment from loan 
 	join borrower on borrower.loan_id = loan.loan_id where borrower.customer_id = :cid'''
	result = db.execute_dql_commands(query, values={'cid':cid})
	loan_info = []
	for row in result:
		loan_info.append({"loan_id": row.loan_id, "loan_type": row.loan_type, "loan_amount": row.loan_amount,"start_date":row.start_date,"monthly_payment":'{0:.3f}'.format(row.monthly_payment)})
	return loan_info




def payBill(cid, aid, lid):
	new_query = '''insert into task values (:cid, :task_type, :task_desc, :done)'''
	task_desc_json = {
		"aid" : aid,
		"lid" : lid
	}
	task_text = json.dumps(task_desc_json)
	db.execute_ddl_and_dml_commands(new_query, values={'cid': cid, 'task_type': 'P', 'task_desc': task_text, 'done': 0})


def fetchEmployeeUsingId(eid):
    query = "SELECT * FROM employee WHERE employee_id = :eid"
    result = db.execute_dql_commands(query, values={'eid': eid})
    for row in result:
        return row

def fetchEmployee(employee_name):
    query = "SELECT * FROM employee WHERE employee_name = :name"
    result = db.execute_dql_commands(query, values={'name': employee_name})
    for row in result:
        return row

def fetchTasks(eid):
    query1 = '''select task.customer_id,task.task_type,task.data,task.done from task
	        join customer on customer.customer_id = task.customer_id
			join branch on branch.branch_city = customer.city_name
			join employee on employee.branch_code = branch.branch_code
			where employee.employee_id = :eid'''
    result1 = db.execute_dql_commands(query1, values={'eid': eid})
    query2 = '''select task.customer_id,task.task_type,task.data,task.done from task
			 where task.customer_id = -1'''
    result2 = db.execute_dql_commands(query2)
    task_info = []
    for row in result1:
        task_info.append({"customer_id": row.customer_id, "task_type": row.task_type, 'task_desc': row.data, 'done': row.done})
    for row in result2:
        task_info.append({"customer_id": row.customer_id, "task_type": row.task_type, 'task_desc': row.data, 'done': row.done})
    return task_info


def completeTask(task_info, index):
    query = '''
    update task
    set done = 1 
    where customer_id = :cid and
    task_type = :t_type and
    data = :t_data'''
    db.execute_ddl_and_dml_commands(query, values={'cid': task_info[int(index)-1]['customer_id'], 't_type': task_info[int(index)-1]['task_type'], 't_data': task_info[int(index)-1]['task_desc']})



def grantSuper():
    query = '''alter function Show_balance owner to postgres;
    alter procedure Deposit owner to postgres;
    alter procedure Withdraw owner to postgres;
    alter procedure Transfer owner to postgres;
    alter procedure create_new_account owner to postgres;
    alter procedure create_another_account owner to postgres;
    alter procedure create_loan owner to postgres;
    alter procedure pay_bills owner to postgres;
    alter function give_bal owner to postgres;
    alter function get_payment owner to postgres;
    alter function update_payment owner to postgres''' 
def grantOfficer():
    query = '''grant usage on schema public to officer;
    grant select on all tables in schema public to officer;
    grant select on employee to officer;
    grant execute on all functions in schema public to officer;
    grant execute on all procedures in schema public to officer;
    grant create on schema public to officer;
    grant insert, update, delete, trigger, references, truncate on branch, loan, customer, payment, account, depositor, borrower, task, payment_log to officer;
    '''
    db.execute_ddl_and_dml_commands(query)

def grantManager():
    query = '''grant all privileges on schema public to manager;
    grant create on schema public to manager;
    '''
    db.execute_ddl_and_dml_commands(query)


def grantCustomer():
    query = '''grant select on customer, account, loan, payment to customer_of_bank;
    grant select, insert on task to customer_of_bank;
    '''
    db.execute_ddl_and_dml_commands(query)

def runQuery(task_info, index):
    if(task_info[int(index)-1]['task_type']=="L"):
        queryL = '''
        call create_loan(:cid, :l_amount, :l_type, :l_duration, :int_rate);
        '''
        cid = task_info[int(index)-1]['customer_id']
        l_amount = eval(task_info[int(index)-1]['task_desc'])['l_amount']
        l_type = eval(task_info[int(index)-1]['task_desc'])['l_type']
        l_duration = eval(task_info[int(index)-1]['task_desc'])['l_duration']
        int_rate = eval(task_info[int(index)-1]['task_desc'])['int_rate']
        db.execute_ddl_and_dml_commands(queryL, values={'cid': cid, 'l_amount': l_amount, 'l_type': l_type, 'l_duration': l_duration, 'int_rate': int_rate})
    
    
    if (task_info[int(index)-1]['task_type']=="E"):
         
        queryE = '''        call create_another_account(:cid, :acc_type);
                '''
        cid = task_info[int(index)-1]['customer_id']
        acc_type = eval(task_info[int(index)-1]['task_desc'])['acc_type']
        db.execute_ddl_and_dml_commands(queryE, values={'cid':cid, 'acc_type': acc_type})
    
    if (task_info[int(index)-1]['task_type']=="T"):
         
        queryT = '''call Transfer(:sid, :rid, :amount)'''
        sid = eval(task_info[int(index)-1]['task_desc'])['sid']
        rid = eval(task_info[int(index)-1]['task_desc'])['rid']
        amount = eval(task_info[int(index)-1]['task_desc'])['amount']
        db.execute_ddl_and_dml_commands(queryT, values={'sid': sid, 'rid': rid, 'amount': amount})
    
    if(task_info[int(index)-1]['task_type']=="N"):
        queryN = '''call create_new_account(:fullname, :dob, :c_name, :s_name, :p_no, :acc_type);
        '''
        fullname = eval(task_info[int(index)-1]['task_desc'])['fullname']
        dob = eval(task_info[int(index)-1]['task_desc'])['dob']
        c_name = eval(task_info[int(index)-1]['task_desc'])['c_name']
        s_name = eval(task_info[int(index)-1]['task_desc'])['s_name']
        p_no = eval(task_info[int(index)-1]['task_desc'])['p_no']
        acc_type = eval(task_info[int(index)-1]['task_desc'])['acc_type']
        db.execute_ddl_and_dml_commands(queryN, values={'fullname': fullname, 'dob': dob, 'c_name': c_name, 's_name': s_name, 'p_no': p_no, 'acc_type': acc_type})

    if(task_info[int(index)-1]['task_type']=="W"):
        queryW = '''call Withdraw(:amount, :aid)'''
        amount = eval(task_info[int(index)-1]['task_desc'])['amount']
        aid = eval(task_info[int(index)-1]['task_desc'])['aid']
        db.execute_ddl_and_dml_commands(queryW, values={'amount': amount, 'aid': aid})
    
    if(task_info[int(index)-1]['task_type']=="D"):
         
        queryD = '''call Deposit(:amount, :aid);'''
        amount = eval(task_info[int(index)-1]['task_desc'])['amount']
        aid = eval(task_info[int(index)-1]['task_desc'])['aid']
        db.execute_ddl_and_dml_commands(queryD, values={'amount': amount, 'aid': aid})

    if(task_info[int(index)-1]['task_type']=="P"):
         
        queryP = '''call pay_bills(:cid, :aid, :lid);
        '''
        cid = task_info[int(index)-1]['customer_id']
        aid = eval(task_info[int(index)-1]['task_desc'])['aid']
        lid = eval(task_info[int(index)-1]['task_desc'])['lid']
        db.execute_ddl_and_dml_commands(queryP, values={'cid': cid, 'aid': aid, 'lid': lid})
    
    

@app.route('/')
def home(): 
    grantSuper()
    changeRole('postgres')
    grantManager()
    grantOfficer()
    grantCustomer()
    return render_template("index.html", title = "Bank System")


@app.route('/<customer_name>/newAccount', methods = ["GET", "POST"])
def newAccount(customer_name):
    customer = fetchCustomer(customer_name)
    cid = customer.customer_id
    if request.method == "GET":
        return render_template("newAccount.html", form_url = f"/{customer_name}/newAccount")
    acc_type = request.form["acc_type"]
    createNewAccount(cid, acc_type)
    flash('New account will be created, Please Wait')
    return redirect(url_for("customer_dashboard", customer_name = customer_name))


@app.route('/register', methods = ["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    fullname = request.form["fullname"]
    acc_type = request.form["acc_type"]
    dob = request.form["dob"]
    c_name = request.form["c_name"]
    s_name = request.form["s_name"]
    p_no = request.form["p_no"]
    createNewCustomer(fullname, dob, c_name, s_name, p_no, acc_type)
    flash('Registration requested successfully, Please Wait')
    return redirect(url_for("register"))


@app.route('/clogin', methods = ["GET", "POST"])
def clogin():
    if request.method == "GET":
        return render_template("clogin.html")
    cid = request.form["cid"]
    customer = fetchCustomerUsingId(int(cid))
    if not customer:
        flash("No such customer exists!")
        return redirect(url_for("clogin"))
    changeRole('customer_of_bank')
    grantCustomer()
    flash("Login Successful")
    return redirect(url_for("customer_dashboard", customer_name = customer.customer_name))

@app.route('/elogin', methods = ["GET", "POST"])
def elogin():
    if request.method == "GET":
        return render_template("elogin.html")
    eid = request.form["eid"]
    employee = fetchEmployeeUsingId(int(eid))
    if not employee:
        flash("No such Employee exists!")
        return redirect(url_for("elogin"))
    
    if employee.employee_role == "Manager":
        changeRole('manager')
    else:
        changeRole('officer')
    flash("Login Successful")
    return redirect(url_for("employee_edashboard", employee_name = employee.employee_name))


@app.route('/<employee_name>/edashboard', methods = ["GET", "POST"])
def employee_edashboard(employee_name):
    employee = fetchEmployee(employee_name)
    task = fetchTasks(employee.employee_id)
    if employee.employee_role == "Manager":
        changeRole('manager')
    else:
        changeRole('officer')
    # loan_info = fetchLoanDetails(customer.customer_id)
    user = checkUser()
    if not employee:
        return "Employee not found", 404  # Display a 404 page if customer not found
    if request.method == "GET":
        return render_template("employee_dashboard.html", title="Employee Dashboard", employee=employee, task = task, user = user)
    index = request.form['index']
    runQuery(task, index)
    completeTask(task, index)
    return redirect(url_for('employee_edashboard', employee_name = employee_name))


@app.route('/<customer_name>/dashboard')
def customer_dashboard(customer_name):
    customer = fetchCustomer(customer_name)
    loan_info = fetchLoanDetails(customer.customer_id)
    user = checkUser()
    if not customer:
        return "Customer not found", 404  # Display a 404 page if customer not found
    return render_template("customer_dashboard.html", title="Customer Dashboard", customer=customer, form_url = f"/{customer_name}/balanceInfo", transfer_link = f"/{customer_name}/transferMoney", newAcc_link = f"/{customer_name}/newAccount", withdraw_link = f"/{customer_name}/withdraw", deposit_link = f"/{customer_name}/deposit", loan_link = f"/{customer_name}/loan", payBill_link = f"/{customer_name}/payBill", loan_info = loan_info, user = user)

@app.route('/<customer_name>/balanceInfo', methods=['POST'])
def check_balance(customer_name):
    customer = fetchCustomer(customer_name)
    customer_id = customer.customer_id
    account_info = fetchCustomerAccBalance(customer_id)
    return render_template("balanceInfo.html", title="BalanceInfo", customer = customer, info = account_info)

@app.route('/<customer_name>/withdraw', methods = ["GET", "POST"])
def withdrawCheck(customer_name):
    customer = fetchCustomer(customer_name)
    customer_id = customer.customer_id
    query = '''select Account.account_id, Account.account_type from Customer, Depositor, Account
                where Customer.customer_id = :cid 
                and Customer.customer_id = Depositor.customer_id
                and Depositor.account_id = Account.account_id;'''
    result = db.execute_dql_commands(query, values={'cid': customer_id})
    if request.method == "GET":
        return render_template("withdraw.html", withdraw_link = f"/{customer.customer_name}/withdraw", result = result)
    aid = request.form["account_choice"]
    amount = request.form["withdraw_value"]
    withdrawMoney(customer_id,amount, aid)
    flash(f'Withdraw of {amount} is requested, Please Wait')
    return redirect(url_for("customer_dashboard", customer_name = customer_name))

@app.route('/<customer_name>/deposit', methods = ["GET", "POST"])
def depositCheck(customer_name):
    customer = fetchCustomer(customer_name)
    customer_id = customer.customer_id
    query = '''select Account.account_id, Account.account_type from Customer, Depositor, Account
                where Customer.customer_id = :cid 
                and Customer.customer_id = Depositor.customer_id
                and Depositor.account_id = Account.account_id;'''
    result = db.execute_dql_commands(query, values={'cid': customer_id})
    if request.method == "GET":
        return render_template("deposit.html", deposit_link = f"/{customer.customer_name}/deposit", result = result)
    aid = request.form["account_choice"]
    amount = request.form["deposit_value"]
    depositMoney(customer_id,amount, aid)
    flash(f'Deposit of {amount} is requested, Please Wait')
    return redirect(url_for("customer_dashboard", customer_name = customer_name))



@app.route('/<customer_name>/transferMoney')
def transfer_money(customer_name):
    customer = fetchCustomer(customer_name)
    customer_id = customer.customer_id
    query = '''select Account.account_id, Account.account_type from Customer, Depositor, Account
                where Customer.customer_id = :cid 
                and Customer.customer_id = Depositor.customer_id
                and Depositor.account_id = Account.account_id;'''
    result = db.execute_dql_commands(query, values={'cid': customer_id})
    return render_template("transfer_window.html", title = "Money Transfer", transfer_link = f"/{customer.customer_name}/transferMoney", result = result)

@app.route('/<customer_name>/transferMoney', methods = ["POST"])
def successful_transfer(customer_name):
    customer = fetchCustomer(customer_name)
    sid = request.form['account_choice']
    amount = 0.0
    rid = request.form['receiver_account']
    if not fetchAccount(rid):
        flash('Receiver is not among our customers, Check spelling properly sulliga')
        return redirect(url_for('transfer_money', customer_name = customer_name))
    try:
        amount = float(request.form['transfer_value'])
    except Exception as e:
        flash('Amount should be a numeric phuka')
        return redirect(url_for('transfer_money', customer_name = customer_name))
    transferAmount(customer.customer_id, sid, rid, amount)
    flash('Money will be transferred, Please Wait')
    return redirect(url_for('customer_dashboard', customer_name = customer_name))


@app.route("/<customer_name>/loan", methods = ["GET", "POST"])
def loanWindow(customer_name):
    customer = fetchCustomer(customer_name)
    if request.method == "GET":
        return render_template("loan.html", loan_link = f"/{customer_name}/loan")
    int_list = {"Education Loan": 4.5, "Business Loan": 7.5, "House Loan": 6, "Personal Loan": 7, "Car Loan": 6.5, "Land Loan": 5.5}
    cid = customer.customer_id
    l_amount = request.form["loan_amount"]
    l_type = request.form["loan_type"]
    l_duration = request.form["loan_duration"]
    int_rate = int_list[l_type]
    createLoan(cid, l_amount, l_type, l_duration, int_rate)
    # return f"{result}"
    flash(f"You have been requested for a loan of {l_amount}, Please Wait")
    return redirect(url_for("customer_dashboard", customer_name = customer_name))

@app.route("/<customer_name>/payBill", methods = ["GET", "POST"])
def payBillWindow(customer_name):
    customer = fetchCustomer(customer_name)
    customer_id = customer.customer_id
    query = '''select Account.account_id, Account.account_type from Customer, Depositor, Account
                where Customer.customer_id = :cid 
                and Customer.customer_id = Depositor.customer_id
                and Depositor.account_id = Account.account_id;'''
    acc_details = db.execute_dql_commands(query, values={'cid': customer_id})
    loan_details = fetchLoanDetails(customer_id)
    if request.method == "GET":
        return render_template("payBill.html", payBill_link = f"/{customer_name}/payBill", acc_details = acc_details, loan_details = loan_details)
    aid = request.form["account_choice"]
    lid = request.form["loan_choice"]
    # return f"{customer_id}, {aid}, {lid}"
    payBill(customer_id, aid, lid)
    flash("Payment requested, Please Wait")
    return redirect(url_for("customer_dashboard", customer_name = customer_name))
if __name__ == "__main__":
    run_begin()
    app.run(debug=True)