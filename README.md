# TP IOT
## Arborescence des fichiers :
    docker/             contient les configurations pour l'environnement docker
    hardware.py         module python de contrôle matériel
    mqtt_client.py      interface en python pour l'envoi des données vers le mosquitto
    
## Utilisation avec l'emulateur
Installez simplement sense-emu :
```bash
sudo apt-get install python3-sense-emu sense-emu-tools
```

## Tests sans connexion a nodeRed
```bash
python3 ./hardware.py
```

## Tests en connexion :
Dans le fichier mqtt_client.py, configurez l'ip / port / identifiants du serveur

Lancez la commande :
```bash
python3 ./mqtt_client.py
```
L'application se connectera dès que le serveur est disponible

## Lancement de mosquitto, nodered, influxdb et mongodb

```bash
cd docker
docker-compose up
```