from flask import Flask, render_template, request, redirect, session, flash
import os
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
import mysql.connector

app = Flask(__name__)
app.secret_key = "secret"

UPLOAD_FOLDER = "static/uploads/"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

model = load_model('model/vgg16_skin_cancer.h5')

# Connexion base de données
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="skin_cancer_db"
)
cursor = db.cursor(dictionary=True)

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["username"]
        pwd  = request.form["password"]
        cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (user, pwd))
        result = cursor.fetchone()
        if result:
            session["user"] = user
            flash("Login réussi ✓", "success")
            return redirect("/dashboard")
        else:
            flash("Erreur login ✗", "danger")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    return render_template("dashboard.html")

@app.route("/predict", methods=["GET", "POST"])
def predict():
    if "user" not in session:
        return redirect("/")
    if request.method == "POST":
        try:
            name = request.form["name"]
            age  = request.form["age"]
            file = request.files["image"]
            if file.filename == "":
                flash("Veuillez choisir une image", "warning")
                return redirect("/predict")
            path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(path)
            import cv2
            img = cv2.imread(path)
            img = cv2.resize(img, (224, 224))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = img / 255.0
            img = np.expand_dims(img, axis=0)
            pred   = model.predict(img)[0][0]
            result = "Malignant" if pred > 0.5 else "Benign"
            cursor.execute(
                "INSERT INTO patients (name, age, result, probability, image_path, created_by) VALUES (%s,%s,%s,%s,%s,%s)",
                (name, age, result, float(pred), path, session["user"])
            )
            db.commit()
            flash("Analyse réussie ✓", "success")
            return render_template("result.html",
                                   result=result,
                                   prob=round(pred * 100, 2),
                                   img=path)
        except Exception as e:
            flash(f"Erreur système : {e}", "danger")
            return redirect("/predict")
    return render_template("predict.html")

@app.route("/patients")
def patients():
    if "user" not in session:
        return redirect("/")
    user = session["user"]
    cursor.execute(
        "SELECT * FROM patients WHERE created_by=%s ORDER BY created_at DESC",
        (user,)
    )
    data = cursor.fetchall()
    return render_template("patients.html", patients=data)

@app.route("/logout")
def logout():
    session.clear()
    flash("Déconnecté", "info")
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirm  = request.form["confirm"]

        if password != confirm:
            flash("Les mots de passe ne correspondent pas !", "danger")
            return redirect("/register")

        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        existing = cursor.fetchone()

        if existing:
            flash("Ce nom d'utilisateur existe déjà !", "warning")
            return redirect("/register")

        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)",
                       (username, password))
        db.commit()
        flash("Compte créé avec succès ! Connectez-vous.", "success")
        return redirect("/")

    return render_template("register.html")

if __name__ == "__main__":
    app.run(debug=True)