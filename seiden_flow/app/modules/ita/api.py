from __future__ import annotations
from flask import Blueprint,jsonify,render_template,request

def create_ita_blueprint(repo,version,ingress_path_fn,timezone_name):
    bp=Blueprint('ita',__name__)
    @bp.get('/ita')
    @bp.get('/intelligence/ita')
    def portal():return render_template('ita_portal.html',version=version,ingress_path=ingress_path_fn(),display_timezone=timezone_name)
    @bp.get('/api/v1/ita/systems')
    def systems():return jsonify({'items':repo.systems()})
    @bp.get('/api/v1/ita/portfolio')
    def portfolio():return jsonify(repo.portfolio())
    @bp.get('/api/v1/ita/systems/<system_id>/current')
    def current(system_id):
        result=repo.current(system_id)
        return (jsonify(result),200) if result else (jsonify({'error':'system_not_found'}),404)
    @bp.get('/api/v1/ita/systems/<system_id>/history')
    def history(system_id):return jsonify(repo.history(system_id,request.args.get('hours',24)))
    return bp
