from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///foro.db"
app.config["SECRET_KEY"] = "cambia-esto-por-una-clave-secreta-real-en-produccion"
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Inicia sesión para continuar."


# ---------- MODELO ----------

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre_usuario = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def cargar_usuario(user_id):
    return Usuario.query.get(int(user_id))


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    autor = db.Column(db.String(80), nullable=False)
    provincia = db.Column(db.String(80), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # "denuncia" o "meme"
    titulo = db.Column(db.String(200), nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    imagen = db.Column(db.String(300), nullable=True)  # URL de imagen (opcional)
    likes = db.Column(db.Integer, default=0)
    comentarios = db.Column(db.Integer, default=0)  # ya no se usa para contar, se deja por compatibilidad
    fecha = db.Column(db.DateTime, default=datetime.utcnow)


class Comentario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    autor = db.Column(db.String(80), nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    post = db.relationship("Post", backref=db.backref("lista_comentarios", order_by="Comentario.fecha"))


# ---------- RUTAS ----------

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nombre_usuario = request.form["nombre_usuario"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if Usuario.query.filter_by(nombre_usuario=nombre_usuario).first():
            return render_template("registro.html", error="Ese nombre de usuario ya existe.")
        if Usuario.query.filter_by(email=email).first():
            return render_template("registro.html", error="Ese correo ya está registrado.")
        if len(password) < 6:
            return render_template("registro.html", error="La contraseña debe tener al menos 6 caracteres.")

        nuevo_usuario = Usuario(nombre_usuario=nombre_usuario, email=email)
        nuevo_usuario.set_password(password)
        db.session.add(nuevo_usuario)
        db.session.commit()

        login_user(nuevo_usuario)
        return redirect(url_for("inicio"))

    return render_template("registro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nombre_usuario = request.form["nombre_usuario"].strip()
        password = request.form["password"]

        usuario = Usuario.query.filter_by(nombre_usuario=nombre_usuario).first()
        if usuario and usuario.check_password(password):
            login_user(usuario)
            siguiente = request.args.get("next")
            return redirect(siguiente or url_for("inicio"))

        return render_template("login.html", error="Usuario o contraseña incorrectos.")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("inicio"))


@app.route("/")
def inicio():
    tipo = request.args.get("tipo")  # denuncia, meme, gobierno, infraestructura o None

    consulta = Post.query
    if tipo:
        consulta = consulta.filter_by(tipo=tipo)

    publicaciones = consulta.order_by(Post.fecha.desc()).all()
    return render_template("index.html", publicaciones=publicaciones, filtro_activo=tipo)


@app.route("/publicar", methods=["GET", "POST"])
@login_required
def publicar():
    if request.method == "POST":
        nuevo_post = Post(
            autor=current_user.nombre_usuario,
            provincia=request.form["provincia"],
            tipo=request.form["tipo"],
            titulo=request.form["titulo"],
            contenido=request.form["contenido"],
            imagen=request.form.get("imagen") or None,
        )
        db.session.add(nuevo_post)
        db.session.commit()
        return redirect(url_for("inicio"))

    return render_template("publicar.html")


@app.route("/post/<int:post_id>/like", methods=["POST"])
def dar_like(post_id):
    post = Post.query.get_or_404(post_id)
    post.likes += 1
    db.session.commit()
    destino = request.referrer or url_for("inicio")
    return redirect(f"{destino}#post-{post_id}")


@app.route("/post/<int:post_id>")
def ver_post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template("post.html", post=post)


@app.route("/post/<int:post_id>/comentar", methods=["POST"])
@login_required
def comentar(post_id):
    post = Post.query.get_or_404(post_id)
    nuevo_comentario = Comentario(
        post_id=post.id,
        autor=current_user.nombre_usuario,
        contenido=request.form["contenido"],
    )
    db.session.add(nuevo_comentario)
    db.session.commit()
    return redirect(url_for("ver_post", post_id=post.id) + "#comentarios")


# ---------- DATOS DE EJEMPLO (solo la primera vez) ----------

def cargar_datos_ejemplo():
    if Post.query.count() == 0:
        db.session.add_all([
            Post(
                autor="Juan Pérez",
                provincia="Santo Domingo",
                tipo="denuncia",
                titulo="Apagón de 8 horas en Los Alcarrizos",
                contenido="Sin luz desde ayer en la tarde. Ya reportamos a la distribuidora y no hay respuesta.",
                imagen="https://commons.wikimedia.org/wiki/Special:FilePath/Electric_transmission_lines.jpg",
                likes=34,
                comentarios=12,
            ),
            Post(
                autor="María Santos",
                provincia="Santiago",
                tipo="meme",
                titulo="Cuando prometen arreglar la calle antes de las elecciones",
                contenido="Y después... nada 😂",
                imagen="https://commons.wikimedia.org/wiki/Special:FilePath/Newport_Whitepit_Lane_pot_hole.JPG",
                likes=210,
                comentarios=45,
            ),
            Post(
                autor="Carlos Reyes",
                provincia="Santo Domingo",
                tipo="gobierno",
                titulo="Nuevo decreto sobre tarifas eléctricas",
                contenido="El Poder Ejecutivo anunció ajustes en las tarifas del sector energético para el próximo trimestre.",
                imagen="https://commons.wikimedia.org/wiki/Special:FilePath/Presidential_Palace_in_the_Dominican_Republic.jpg",
                likes=58,
                comentarios=20,
            ),
            Post(
                autor="Ana Ramírez",
                provincia="La Romana",
                tipo="infraestructura",
                titulo="Avanza construcción de nuevo complejo turístico",
                contenido="El proyecto promete generar cientos de empleos directos e indirectos en la región Este.",
                imagen="https://commons.wikimedia.org/wiki/Special:FilePath/Construction_Crane_Residential_Building_I.jpg",
                likes=76,
                comentarios=15,
            ),
        ])
        db.session.commit()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        cargar_datos_ejemplo()
    app.run(debug=True)
